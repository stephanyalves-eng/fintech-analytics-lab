-- Analytical marts (data_origin = derived). Grain stated per table.

-- mart_auth_daily · grain: local creation date x country x currency x method.
-- Attempts are attributed to the payment's creation date (metric catalog period rule).
CREATE OR REPLACE TABLE mart_auth_daily AS
SELECT created_date_local, country, currency, method_code,
       COUNT(*)                                        AS payments,
       COUNT(*) FILTER (WHERE is_succeeded)            AS succeeded_payments,
       SUM(n_attempts)                                 AS attempts,
       SUM(n_approved)                                 AS approved_attempts,
       SUM(n_error)                                    AS error_attempts,
       SUM(n_approved) / SUM(n_attempts)               AS m01_attempt_auth_rate,
       COUNT(*) FILTER (WHERE is_succeeded) / COUNT(*) AS m02_payment_success_rate,
       COALESCE(SUM(amount) FILTER (WHERE is_succeeded), 0)     AS m06_tpv_local,
       COALESCE(SUM(amount_brl) FILTER (WHERE is_succeeded), 0) AS m07_tpv_brl,
       SUM(processing_cost_brl)                        AS m08_processing_cost_brl
FROM fct_payment
GROUP BY ALL;

-- mart_acquirer_performance · grain: local month x acquirer x method x amount band (attempts).
CREATE OR REPLACE TABLE mart_acquirer_performance AS
SELECT created_month_local, country, acquirer_id, method_code, amount_band_brl,
       COUNT(*)                                                 AS attempts,
       COUNT(*) FILTER (WHERE result = 'approved')              AS approved,
       COUNT(*) FILTER (WHERE decline_category = 'soft')        AS declined_soft,
       COUNT(*) FILTER (WHERE decline_category = 'hard')        AS declined_hard,
       COUNT(*) FILTER (WHERE result = 'error')                 AS errors,
       COUNT(*) FILTER (WHERE result = 'approved') / COUNT(*)   AS m01_attempt_auth_rate,
       COUNT(*) FILTER (WHERE result = 'error') / COUNT(*)      AS m10_technical_error_rate,
       quantile_cont(latency_ms, 0.50)                          AS m11_latency_p50_ms,
       quantile_cont(latency_ms, 0.95)                          AS m11_latency_p95_ms,
       SUM(processing_cost_brl)                                 AS m08_processing_cost_brl
FROM fct_attempt
GROUP BY ALL;

-- mart_decline_reasons · grain: local month x country x method x decline code (failed attempts).
CREATE OR REPLACE TABLE mart_decline_reasons AS
WITH f AS (
    SELECT created_month_local, country, method_code, decline_code, decline_category,
           reason_group, COUNT(*) AS failed_attempts
    FROM fct_attempt
    WHERE result IN ('declined', 'error')
    GROUP BY ALL
)
SELECT f.*,
       failed_attempts / SUM(failed_attempts) OVER (
           PARTITION BY created_month_local, country, method_code
       ) AS m04_decline_share
FROM f;

-- mart_retry_recovery · grain: country x method x first-attempt category x first acquirer.
-- Denominator of M05: payments whose FIRST attempt failed soft or technical.
CREATE OR REPLACE TABLE mart_retry_recovery AS
SELECT country, method_code, first_category, first_acquirer_id,
       COUNT(*)                                              AS payments_first_failed,
       COUNT(*) FILTER (WHERE n_attempts > 1)                AS payments_retried,
       COUNT(*) FILTER (WHERE recovered_by_retry)            AS payments_recovered,
       COUNT(*) FILTER (WHERE recovered_by_retry) / COUNT(*) AS m05_retry_recovery_rate,
       SUM(processing_cost_brl)                              AS processing_cost_brl
FROM fct_payment
WHERE first_failed_retryable
GROUP BY ALL;

-- mart_merchant_cohorts · grain: cohort type x cohort month x months since cohort.
-- Cohort = ACTIVATION month (dim_merchant), not first observed payment month (audit M5).
-- Merchants activated before the data window are left-censored: they form a separate
-- 'pre_window' cohort anchored at the first window month and must not be read as new merchants.
-- cohort_size counts every merchant of the cohort (incl. ones with no payment), so retention
-- = active merchants / cohort size. NOTE: the generator models no churn, so retention is ~1 by
-- construction; this mart demonstrates the SQL pattern, not a merchant-retention finding.
CREATE OR REPLACE TABLE mart_merchant_cohorts AS
WITH win AS (
    SELECT MIN(created_month_local) AS start_month FROM fct_payment
),
m AS (
    SELECT d.merchant_id,
           CASE WHEN d.activation_date >= win.start_month THEN 'activated_in_window'
                ELSE 'pre_window' END                                        AS cohort_type,
           GREATEST(CAST(date_trunc('month', d.activation_date) AS DATE), win.start_month)
                                                                             AS cohort_month
    FROM dim_merchant AS d, win
),
sizes AS (
    SELECT cohort_type, cohort_month, COUNT(*) AS cohort_size FROM m GROUP BY ALL
),
monthly AS (
    SELECT merchant_id, created_month_local AS activity_month,
           COUNT(*) AS payments,
           COUNT(*) FILTER (WHERE is_succeeded) AS succeeded_payments,
           COALESCE(SUM(amount_brl) FILTER (WHERE is_succeeded), 0) AS tpv_brl
    FROM fct_payment
    GROUP BY ALL
),
act AS (
    SELECT m.cohort_type, m.cohort_month, mo.*,
           date_diff('month', m.cohort_month, mo.activity_month) AS months_since_cohort
    FROM monthly AS mo
    JOIN m USING (merchant_id)
)
SELECT a.cohort_type, a.cohort_month, a.months_since_cohort,
       ANY_VALUE(s.cohort_size)                                  AS cohort_size,
       COUNT(DISTINCT a.merchant_id)                             AS active_merchants,
       COUNT(DISTINCT a.merchant_id) / ANY_VALUE(s.cohort_size)  AS merchant_retention,
       SUM(a.payments)                                           AS payments,
       SUM(a.succeeded_payments) / SUM(a.payments)               AS m02_payment_success_rate,
       SUM(a.tpv_brl)                                            AS m07_tpv_brl
FROM act AS a
JOIN sizes AS s USING (cohort_type, cohort_month)
GROUP BY a.cohort_type, a.cohort_month, a.months_since_cohort;
