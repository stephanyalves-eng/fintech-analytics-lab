-- P1.4 diagnostics (data_origin = derived from synthetic data). Each `-- name:` block is one
-- query; metric IDs refer to docs/metric_catalog.md. DESCRIPTIVE ONLY: no causal reading.

-- name: d01_failure_taxonomy
-- P1.4.b · grain: country x result x failure category x reason group (attempts).
-- Shares use ALL attempts of the country as denominator (M03 / M10), and failed attempts
-- (declined + error) as denominator of share_of_failed (M04 rolled up to reason group).
WITH c AS (
    SELECT country, result,
           COALESCE(decline_category, 'approved') AS category,
           COALESCE(reason_group, 'approved')     AS reason_group,
           COUNT(*)                               AS attempts
    FROM fct_attempt
    GROUP BY ALL
)
SELECT *,
       attempts / SUM(attempts) OVER (PARTITION BY country) AS share_of_attempts,
       CASE WHEN result <> 'approved'
            THEN attempts / SUM(attempts) FILTER (WHERE result <> 'approved')
                                          OVER (PARTITION BY country)
       END                                                  AS share_of_failed
FROM c
ORDER BY country, result, attempts DESC;

-- name: d02_segment_success
-- P1.4.a · grain: country x method x amount band x sector (payments). M02 per segment and the
-- country x method baseline; lost_vs_baseline = payments x (baseline M02 - segment M02).
-- Ranking by lost payments is descriptive; segment gaps mix risk, ticket and issuer effects.
WITH seg AS (
    SELECT country, method_code, amount_band_brl, sector,
           COUNT(*)                             AS payments,
           COUNT(*) FILTER (WHERE is_succeeded) AS succeeded
    FROM fct_payment
    GROUP BY ALL
),
base AS (
    SELECT country, method_code,
           SUM(succeeded) / SUM(payments) AS baseline_m02
    FROM seg
    GROUP BY ALL
)
SELECT seg.*, succeeded / payments AS m02, base.baseline_m02,
       payments * (base.baseline_m02 - succeeded / payments) AS lost_vs_baseline
FROM seg
JOIN base USING (country, method_code)
ORDER BY lost_vs_baseline DESC;

-- name: d03_error_rate_by_period
-- P1.4.b · grain: acquirer x local-hour period (attempts). M10 in peak (19-22h local) vs
-- off-peak, so technical failures are separated from issuer declines.
SELECT country, acquirer_id,
       CASE WHEN attempted_hour_local BETWEEN 19 AND 22 THEN 'peak 19-22h' ELSE 'off-peak' END
                                                              AS period,
       COUNT(*)                                               AS attempts,
       COUNT(*) FILTER (WHERE result = 'error')               AS errors,
       COUNT(*) FILTER (WHERE result = 'error') / COUNT(*)    AS m10_technical_error_rate
FROM fct_attempt
GROUP BY ALL
ORDER BY country, acquirer_id, period;

-- name: s1_reroute_base
-- S1 input · grain: country x first acquirer x method x amount band x switched-at-retry (payments).
-- Population: card payments whose 1st attempt was a SOFT decline AND that were retried.
-- switched = attempt 2 went to a different acquirer. Costs/fees in BRL (payment FX).
WITH a2 AS (
    SELECT payment_id, acquirer_id AS retry_acquirer_id, switched_acquirer
    FROM fct_attempt
    WHERE attempt_no = 2
),
fee AS (
    SELECT s.payment_id, s.fee AS fee_local
    FROM stg_settlement AS s
)
SELECT p.country, p.first_acquirer_id, p.method_code, p.amount_band_brl,
       a2.switched_acquirer                                       AS switched,
       COUNT(*)                                                   AS payments,
       COUNT(*) FILTER (WHERE p.is_succeeded)                     AS succeeded,
       SUM(p.amount_brl)                                          AS amount_brl,
       COALESCE(SUM(p.amount_brl) FILTER (WHERE p.is_succeeded), 0) AS tpv_brl,
       SUM(p.processing_cost_brl)                                 AS processing_cost_brl,
       COALESCE(SUM(fee.fee_local * p.rate_to_brl), 0)            AS fee_brl
FROM fct_payment AS p
JOIN a2 USING (payment_id)
LEFT JOIN fee USING (payment_id)
WHERE p.first_category = 'soft' AND p.method_code <> 'pix'
GROUP BY ALL
ORDER BY ALL;

-- name: s2_retry_base
-- S2 input · grain: country (payments + attempt-3 facts). Everything needed to recompute
-- outcomes under a retry cap of 2 (inside data support) or 4 (extrapolation).
WITH fee AS (
    SELECT s.payment_id, s.fee AS fee_local FROM stg_settlement AS s
),
pay AS (
    SELECT p.country,
           COUNT(*)                                                     AS payments,
           COUNT(*) FILTER (WHERE p.is_succeeded)                       AS succeeded,
           COALESCE(SUM(p.amount_brl) FILTER (WHERE p.is_succeeded), 0) AS tpv_brl,
           SUM(p.processing_cost_brl)                                   AS processing_cost_brl,
           COALESCE(SUM(fee.fee_local * p.rate_to_brl), 0)              AS fee_brl,
           -- succeeded exactly at attempt 3 (lost under cap = 2)
           COUNT(*) FILTER (WHERE p.is_succeeded AND p.last_attempt_no = 3) AS succ_at_3,
           COALESCE(SUM(p.amount_brl) FILTER (WHERE p.is_succeeded AND p.last_attempt_no = 3), 0)
                                                                        AS tpv_at_3_brl,
           COALESCE(SUM(fee.fee_local * p.rate_to_brl)
                    FILTER (WHERE p.is_succeeded AND p.last_attempt_no = 3), 0) AS fee_at_3_brl
    FROM fct_payment AS p
    LEFT JOIN fee USING (payment_id)
    GROUP BY p.country
),
att AS (
    SELECT country,
           COUNT(*) FILTER (WHERE attempt_no = 3)                          AS attempts_3,
           COALESCE(SUM(processing_cost_brl) FILTER (WHERE attempt_no = 3), 0) AS cost_3_brl,
           COUNT(*) FILTER (WHERE attempt_no = 3 AND result = 'approved')  AS approved_3,
           -- retryable failures at attempts 2 and 3, and how many of attempt-2 ones got retried
           COUNT(*) FILTER (WHERE attempt_no = 2 AND decline_category IN ('soft', 'technical'))
                                                                           AS retryable_fail_2,
           COUNT(*) FILTER (WHERE attempt_no = 2 AND decline_category IN ('soft', 'technical')
                                 AND next_result IS NOT NULL)              AS retried_after_2,
           COUNT(*) FILTER (WHERE attempt_no = 3 AND decline_category IN ('soft', 'technical'))
                                                                           AS retryable_fail_3,
           AVG(processing_cost_brl) FILTER (WHERE result <> 'approved')    AS fixed_cost_per_attempt_brl
    FROM fct_attempt
    GROUP BY country
),
elig AS (
    -- payments whose 3rd attempt failed retryable: the only ones a 4th attempt could recover
    SELECT p.country,
           AVG(p.amount_brl)                AS avg_ticket_eligible_brl
    FROM fct_payment AS p
    JOIN fct_attempt AS a ON a.payment_id = p.payment_id AND a.attempt_no = 3
    WHERE a.decline_category IN ('soft', 'technical')
    GROUP BY p.country
),
var AS (
    -- variable (bps) acquirer cost of approved attempts, as a share of approved amount
    SELECT a.country,
           SUM(a.processing_cost_brl) / SUM(p.amount_brl) AS approved_cost_rate
    FROM fct_attempt AS a
    JOIN fct_payment AS p USING (payment_id)
    WHERE a.result = 'approved'
    GROUP BY a.country
)
SELECT pay.*, att.* EXCLUDE (country), elig.avg_ticket_eligible_brl,
       var.approved_cost_rate
FROM pay
JOIN att USING (country)
LEFT JOIN elig USING (country)
LEFT JOIN var USING (country)
ORDER BY country;
