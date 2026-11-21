-- P1.3 analyses (15). All outputs are `derived` from `synthetic` data.
-- Each `-- name:` block is one query; metric IDs refer to docs/metric_catalog.md.

-- name: q01_daily_trend_7d
-- M01, M02 per country/day with 7-day rolling rates (ratio of rolling sums, not mean of
-- ratios) and week-over-week payment delta. Techniques: date spine, RANGE window, LAG.
WITH spine AS (  -- dense calendar so LAG(.., 7) is exactly 7 days back
    SELECT CAST(t.d AS DATE) AS created_date_local, c.country
    FROM generate_series((SELECT MIN(created_date_local) FROM mart_auth_daily),
                         (SELECT MAX(created_date_local) FROM mart_auth_daily),
                         INTERVAL 1 DAY) AS t(d)
    CROSS JOIN (SELECT DISTINCT country FROM mart_auth_daily) AS c
),
d AS (
    SELECT s.created_date_local, s.country,
           COALESCE(SUM(m.payments), 0) AS payments,
           COALESCE(SUM(m.succeeded_payments), 0) AS succeeded,
           COALESCE(SUM(m.attempts), 0) AS attempts,
           COALESCE(SUM(m.approved_attempts), 0) AS approved
    FROM spine AS s
    LEFT JOIN mart_auth_daily AS m USING (created_date_local, country)
    GROUP BY s.created_date_local, s.country
)
SELECT created_date_local, country, payments,
       approved / attempts                                AS m01_attempt_auth_rate,
       succeeded / payments                               AS m02_payment_success_rate,
       SUM(approved) OVER w7 / SUM(attempts) OVER w7      AS m01_7d,
       SUM(succeeded) OVER w7 / SUM(payments) OVER w7     AS m02_7d,
       payments - LAG(payments, 7) OVER (PARTITION BY country ORDER BY created_date_local)
                                                          AS payments_wow_delta
FROM d
WINDOW w7 AS (PARTITION BY country ORDER BY created_date_local
              RANGE BETWEEN INTERVAL 6 DAY PRECEDING AND CURRENT ROW)
ORDER BY country, created_date_local;

-- name: q02_monthly_tpv
-- M06 (local currency) and M07 (BRL) per month and currency, currency share of consolidated
-- TPV and month-over-month growth. Never sums raw currencies. Techniques: CTE, LAG.
WITH m AS (
    SELECT CAST(date_trunc('month', created_date_local) AS DATE) AS month, currency,
           SUM(m06_tpv_local) AS m06_tpv_local, SUM(m07_tpv_brl) AS m07_tpv_brl
    FROM mart_auth_daily
    GROUP BY ALL
)
SELECT month, currency, m06_tpv_local, m07_tpv_brl,
       m07_tpv_brl / SUM(m07_tpv_brl) OVER (PARTITION BY month)                  AS brl_share,
       m06_tpv_local / LAG(m06_tpv_local) OVER (PARTITION BY currency ORDER BY month) - 1
                                                                                AS mom_growth_local
FROM m
ORDER BY month, currency;

-- name: q03_attempt_vs_payment_rates
-- M01 vs M02 vs M12 by country x method: shows how retries widen the gap between the
-- attempt-level and payment-level rates. Technique: conditional aggregation.
SELECT country, method_code,
       SUM(payments)                                  AS payments,
       SUM(attempts)                                  AS attempts,
       SUM(approved_attempts) / SUM(attempts)         AS m01_attempt_auth_rate,
       SUM(succeeded_payments) / SUM(payments)        AS m02_payment_success_rate,
       SUM(attempts) / SUM(payments)                  AS m12_avg_attempts_per_payment,
       SUM(succeeded_payments) / SUM(payments)
         - SUM(approved_attempts) / SUM(attempts)     AS m02_minus_m01
FROM mart_auth_daily
GROUP BY ALL
ORDER BY country, method_code;

-- name: q04_acquirer_mix_adjusted
-- M01 per card acquirer, raw vs mix-adjusted (direct standardization over method x amount
-- band using the country's attempt mix) to avoid Simpson-style mix effects. Descriptive only.
-- Techniques: CTE, window over aggregate, RANK.
WITH seg AS (
    SELECT country, acquirer_id, method_code, amount_band_brl,
           SUM(attempts) AS attempts, SUM(approved) AS approved
    FROM mart_acquirer_performance
    WHERE method_code <> 'pix'
    GROUP BY ALL
),
w AS (
    SELECT country, method_code, amount_band_brl,
           SUM(attempts) / SUM(SUM(attempts)) OVER (PARTITION BY country) AS seg_weight
    FROM seg
    GROUP BY country, method_code, amount_band_brl
),
r AS (
    SELECT seg.*, seg.approved / seg.attempts AS m01_seg, w.seg_weight
    FROM seg JOIN w USING (country, method_code, amount_band_brl)
)
SELECT country, acquirer_id,
       SUM(attempts)                                   AS attempts,
       SUM(approved) / SUM(attempts)                   AS m01_raw,
       SUM(m01_seg * seg_weight) / SUM(seg_weight)     AS m01_mix_adjusted,
       SUM(seg_weight)                                 AS mix_coverage,
       RANK() OVER (PARTITION BY country
                    ORDER BY SUM(m01_seg * seg_weight) / SUM(seg_weight) DESC) AS rank_adjusted
FROM r
GROUP BY country, acquirer_id
ORDER BY country, rank_adjusted;

-- name: q05_decline_taxonomy
-- M04 top-5 failure codes per country plus category share. Techniques: window shares,
-- QUALIFY + ROW_NUMBER.
WITH c AS (
    SELECT country, decline_category, reason_group, decline_code,
           SUM(failed_attempts) AS failed_attempts
    FROM mart_decline_reasons
    GROUP BY ALL
)
SELECT *,
       failed_attempts / SUM(failed_attempts) OVER (PARTITION BY country) AS m04_share,
       SUM(failed_attempts) OVER (PARTITION BY country, decline_category)
         / SUM(failed_attempts) OVER (PARTITION BY country)               AS category_share
FROM c
QUALIFY ROW_NUMBER() OVER (PARTITION BY country ORDER BY failed_attempts DESC, decline_code) <= 5
ORDER BY country, failed_attempts DESC;

-- name: q06_retry_sequence
-- Marginal M01 by attempt_no, previous failure category (LAG) and whether the retry switched
-- acquirer. Observational: switching is not randomized, so no causal reading.
SELECT attempt_no, prev_category, switched_acquirer,
       COUNT(*)                                              AS attempts,
       COUNT(*) FILTER (WHERE result = 'approved') / COUNT(*) AS m01_attempt_auth_rate
FROM fct_attempt
GROUP BY ALL
ORDER BY attempt_no, prev_category NULLS FIRST, switched_acquirer NULLS FIRST;

-- name: q07_retry_recovery_cost
-- M05 by country x method x first failure category, and processing cost of retry attempts
-- (attempt_no > 1) per recovered payment (BRL). Techniques: CTEs, FILTER, attempt->payment join
-- at payment grain (1:1 on fct_payment).
WITH r AS (
    SELECT country, method_code, first_category,
           COUNT(*)                                    AS payments_first_failed,
           COUNT(*) FILTER (WHERE recovered_by_retry)  AS payments_recovered
    FROM fct_payment
    WHERE first_failed_retryable
    GROUP BY ALL
),
c AS (
    SELECT a.country, a.method_code, p.first_category, SUM(a.processing_cost_brl) AS retry_cost_brl
    FROM fct_attempt AS a
    JOIN fct_payment AS p USING (payment_id)
    WHERE a.attempt_no > 1
    GROUP BY ALL
)
SELECT r.*,
       payments_recovered / payments_first_failed            AS m05_retry_recovery_rate,
       c.retry_cost_brl,
       c.retry_cost_brl / NULLIF(payments_recovered, 0)      AS retry_cost_per_recovered_brl
FROM r
LEFT JOIN c USING (country, method_code, first_category)
ORDER BY country, method_code, first_category;

-- name: q08_retry_timing
-- For each failed attempt: was it retried, how long until the retry (LEAD) and did the retry
-- succeed. Techniques: LEAD, percentiles, conditional average.
WITH s AS (
    SELECT decline_category, result, attempted_at_utc,
           LEAD(attempted_at_utc) OVER w AS next_at,
           LEAD(result) OVER w           AS next_result
    FROM fct_attempt
    WINDOW w AS (PARTITION BY payment_id ORDER BY attempt_no)
)
SELECT decline_category,
       COUNT(*)                                                       AS failed_attempts,
       COUNT(next_at)                                                 AS retried,
       COUNT(next_at) / COUNT(*)                                      AS retry_rate,
       quantile_cont(date_diff('second', attempted_at_utc, next_at), 0.5) AS p50_gap_s,
       quantile_cont(date_diff('second', attempted_at_utc, next_at), 0.9) AS p90_gap_s,
       AVG(CASE WHEN next_result = 'approved' THEN 1.0
                WHEN next_result IS NOT NULL THEN 0.0 END)            AS next_attempt_approval
FROM s
WHERE result <> 'approved'
GROUP BY 1
ORDER BY 1;

-- name: q09_error_rate_peak_hours
-- M10 by acquirer, local peak hours (19-22h) vs off-peak, via conditional aggregation.
SELECT country, acquirer_id,
       COUNT(*) FILTER (WHERE attempted_hour_local BETWEEN 19 AND 22)              AS peak_attempts,
       COUNT(*) FILTER (WHERE attempted_hour_local BETWEEN 19 AND 22 AND result = 'error')
         / COUNT(*) FILTER (WHERE attempted_hour_local BETWEEN 19 AND 22)          AS m10_peak,
       COUNT(*) FILTER (WHERE attempted_hour_local NOT BETWEEN 19 AND 22)          AS offpeak_attempts,
       COUNT(*) FILTER (WHERE attempted_hour_local NOT BETWEEN 19 AND 22 AND result = 'error')
         / COUNT(*) FILTER (WHERE attempted_hour_local NOT BETWEEN 19 AND 22)      AS m10_offpeak
FROM fct_attempt
GROUP BY ALL
ORDER BY country, acquirer_id;

-- name: q10_latency_percentiles
-- M11 p50/p95 per acquirer and result, computed from attempts (percentiles are not additive,
-- so they cannot be re-aggregated from monthly marts).
SELECT acquirer_id, result,
       COUNT(*)                         AS attempts,
       quantile_cont(latency_ms, 0.50)  AS m11_latency_p50_ms,
       quantile_cont(latency_ms, 0.95)  AS m11_latency_p95_ms
FROM fct_attempt
GROUP BY ALL
ORDER BY acquirer_id, result;

-- name: q11_merchant_concentration
-- Merchant TPV (M07, BRL) concentration by decile: NTILE + running cumulative share (Pareto).
WITH m AS (
    SELECT merchant_id, size_tier,
           COALESCE(SUM(amount_brl) FILTER (WHERE is_succeeded), 0) AS tpv_brl
    FROM fct_payment
    GROUP BY ALL
),
r AS (
    SELECT *,
           NTILE(10) OVER (ORDER BY tpv_brl DESC, merchant_id) AS decile,
           SUM(tpv_brl) OVER (ORDER BY tpv_brl DESC, merchant_id ROWS UNBOUNDED PRECEDING)
             / SUM(tpv_brl) OVER ()                            AS cum_share
    FROM m
)
SELECT decile, COUNT(*) AS merchants, SUM(tpv_brl) AS m07_tpv_brl,
       SUM(tpv_brl) / SUM(SUM(tpv_brl)) OVER () AS tpv_share,
       MAX(cum_share)                           AS cum_share_at_decile_end,
       mode(size_tier)                          AS most_common_tier
FROM r
GROUP BY decile
ORDER BY decile;

-- name: q12_cohort_retention
-- Merchant cohort retention matrix (cohort = first local payment month), pivoted with
-- conditional aggregation for months 0..6.
SELECT cohort_month, ANY_VALUE(cohort_size) AS cohort_size,
       MAX(merchant_retention) FILTER (WHERE months_since_cohort = 0) AS m0,
       MAX(merchant_retention) FILTER (WHERE months_since_cohort = 1) AS m1,
       MAX(merchant_retention) FILTER (WHERE months_since_cohort = 2) AS m2,
       MAX(merchant_retention) FILTER (WHERE months_since_cohort = 3) AS m3,
       MAX(merchant_retention) FILTER (WHERE months_since_cohort = 4) AS m4,
       MAX(merchant_retention) FILTER (WHERE months_since_cohort = 5) AS m5,
       MAX(merchant_retention) FILTER (WHERE months_since_cohort = 6) AS m6
FROM mart_merchant_cohorts
GROUP BY cohort_month
ORDER BY cohort_month;

-- name: q13_unit_economics
-- M08, M09 and the ESTIMATED M13/M14 [TO VERIFY: synthetic MDR, not real revenue] per
-- country x method, in BRL using each payment's FX. Payment-grain 1:1 join with settlement.
WITH fee AS (
    SELECT s.payment_id, s.fee * p.rate_to_brl AS fee_brl
    FROM stg_settlement AS s
    JOIN fct_payment AS p USING (payment_id)
)
SELECT p.country, p.method_code,
       COUNT(*) FILTER (WHERE p.is_succeeded)                                   AS succeeded_payments,
       SUM(p.processing_cost_brl)                                               AS m08_processing_cost_brl,
       SUM(p.processing_cost_brl) / COUNT(*) FILTER (WHERE p.is_succeeded)      AS m09_cost_per_success_brl,
       SUM(f.fee_brl) / SUM(p.amount_brl) FILTER (WHERE p.is_succeeded)         AS m13_take_rate_est_to_verify,
       SUM(f.fee_brl) - SUM(p.processing_cost_brl)                              AS m14_net_revenue_est_to_verify
FROM fct_payment AS p
LEFT JOIN fee AS f USING (payment_id)
GROUP BY ALL
ORDER BY p.country, p.method_code;

-- name: q14_anomaly_days
-- Days whose M02 deviates >= 3 sd from the trailing 28-day window (current day excluded).
-- May legitimately return 0 rows. Techniques: ROWS window, STDDEV_SAMP.
WITH d AS (
    SELECT created_date_local, country,
           SUM(succeeded_payments) / SUM(payments) AS m02, SUM(payments) AS payments
    FROM mart_auth_daily
    GROUP BY ALL
),
z AS (
    SELECT *,
           AVG(m02)         OVER w AS mean_28d,
           STDDEV_SAMP(m02) OVER w AS sd_28d,
           COUNT(*)         OVER w AS n_28d
    FROM d
    WINDOW w AS (PARTITION BY country ORDER BY created_date_local
                 ROWS BETWEEN 28 PRECEDING AND 1 PRECEDING)
)
SELECT created_date_local, country, payments, m02, mean_28d, sd_28d,
       (m02 - mean_28d) / sd_28d AS z_score
FROM z
WHERE n_28d = 28 AND sd_28d > 0 AND ABS((m02 - mean_28d) / sd_28d) >= 3
ORDER BY ABS(z_score) DESC;

-- name: q15_double_counting_demo
-- Interview point: joining payments to attempts before summing repeats the payment amount
-- once per attempt. Compares the WRONG join-based TPV with the correct payment-level M06.
WITH correct AS (
    SELECT currency, SUM(amount) AS m06_tpv_correct
    FROM stg_payment WHERE final_status = 'succeeded' GROUP BY 1
),
naive AS (
    SELECT p.currency, SUM(p.amount) AS tpv_naive_join
    FROM stg_payment AS p
    JOIN stg_attempt AS a USING (payment_id)
    WHERE p.final_status = 'succeeded'
    GROUP BY 1
)
SELECT currency, m06_tpv_correct, tpv_naive_join,
       tpv_naive_join / m06_tpv_correct - 1 AS naive_inflation
FROM correct JOIN naive USING (currency)
ORDER BY currency;
