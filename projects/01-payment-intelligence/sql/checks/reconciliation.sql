-- Reconciliation checks on marts. Each `-- name:` block returns VIOLATING rows; 0 rows = pass.

-- name: r01_tpv_not_inflated
-- Test 9: payment-level TPV (marts) = direct sum of succeeded payment amounts in the source,
-- per currency. Retries must not inflate TPV.
WITH src AS (
    SELECT currency, SUM(amount) AS tpv FROM stg_payment WHERE final_status = 'succeeded' GROUP BY 1
),
mart AS (SELECT currency, SUM(m06_tpv_local) AS tpv FROM mart_auth_daily GROUP BY 1),
fct AS (SELECT currency, SUM(amount) FILTER (WHERE is_succeeded) AS tpv FROM fct_payment GROUP BY 1)
SELECT src.currency, src.tpv AS src_tpv, mart.tpv AS mart_tpv, fct.tpv AS fct_tpv
FROM src
FULL JOIN mart USING (currency)
FULL JOIN fct USING (currency)
WHERE src.tpv IS DISTINCT FROM mart.tpv OR src.tpv IS DISTINCT FROM fct.tpv;

-- name: r02_grain_preserved
-- Facts keep their grain (no join fan-out).
SELECT 'fct_payment' AS tbl, n, expected
FROM (SELECT (SELECT COUNT(*) FROM fct_payment) AS n,
             (SELECT COUNT(DISTINCT payment_id) FROM stg_payment) AS expected)
WHERE n <> expected
UNION ALL
SELECT 'fct_attempt', n, expected
FROM (SELECT (SELECT COUNT(*) FROM fct_attempt) AS n,
             (SELECT COUNT(*) FROM stg_attempt) AS expected)
WHERE n <> expected;

-- name: r03_attempt_vs_payment
-- Attempt-level vs payment-level: attempts/approvals agree across marts and source, and
-- succeeded payments = approved attempts (<= 1 approval per payment).
SELECT *
FROM (
    SELECT
        (SELECT COUNT(*) FROM stg_attempt)                           AS src_attempts,
        (SELECT SUM(attempts) FROM mart_auth_daily)                  AS daily_attempts,
        (SELECT SUM(attempts) FROM mart_acquirer_performance)        AS acq_attempts,
        (SELECT COUNT(*) FROM stg_attempt WHERE result = 'approved')  AS src_approved,
        (SELECT SUM(approved_attempts) FROM mart_auth_daily)         AS daily_approved,
        (SELECT SUM(succeeded_payments) FROM mart_auth_daily)        AS daily_succeeded,
        (SELECT COUNT(*) FROM stg_attempt WHERE result <> 'approved') AS src_failed,
        (SELECT SUM(failed_attempts) FROM mart_decline_reasons)      AS decline_failed,
        (SELECT COUNT(*) FROM stg_payment)                           AS src_payments,
        (SELECT SUM(payments) FROM mart_auth_daily)                  AS daily_payments
)
WHERE src_attempts <> daily_attempts OR src_attempts <> acq_attempts
   OR src_approved <> daily_approved OR src_approved <> daily_succeeded
   OR src_failed <> decline_failed OR src_payments <> daily_payments;

-- name: r04_settlement_vs_tpv
-- Settled gross per currency = payment-level TPV per currency.
WITH s AS (SELECT currency, SUM(gross_amount) AS gross FROM stg_settlement GROUP BY 1),
     t AS (SELECT currency, SUM(m06_tpv_local) AS tpv FROM mart_auth_daily GROUP BY 1)
SELECT * FROM s FULL JOIN t USING (currency) WHERE s.gross IS DISTINCT FROM t.tpv;

-- name: r05_shares_and_funnel
-- M04 shares sum to 1 per partition; M05 funnel is monotone (recovered <= retried <= base).
SELECT 'm04' AS rule, CAST(created_month_local AS VARCHAR) || country || method_code AS key
FROM mart_decline_reasons
GROUP BY created_month_local, country, method_code
HAVING ABS(SUM(m04_decline_share) - 1) > 1e-9
UNION ALL
SELECT 'm05', country || method_code || first_category || first_acquirer_id
FROM mart_retry_recovery
WHERE payments_recovered > payments_retried OR payments_retried > payments_first_failed;
