-- Contract checks on the staging layer (acceptance tests of assumptions.md).
-- Each `-- name:` block is one SELECT that returns VIOLATING rows; 0 rows = pass.

-- name: c01_pk_unique
-- Test 1 (PK): every primary key is unique.
SELECT 'dim_merchant' AS tbl, merchant_id AS key FROM stg_merchant GROUP BY 2 HAVING COUNT(*) > 1
UNION ALL SELECT 'dim_acquirer', acquirer_id FROM stg_acquirer GROUP BY 2 HAVING COUNT(*) > 1
UNION ALL SELECT 'dim_payment_method', method_code FROM stg_payment_method GROUP BY 2 HAVING COUNT(*) > 1
UNION ALL SELECT 'dim_decline_code', decline_code FROM stg_decline_code GROUP BY 2 HAVING COUNT(*) > 1
UNION ALL SELECT 'dim_fx_rate', currency || '|' || rate_date FROM stg_fx_rate GROUP BY 2 HAVING COUNT(*) > 1
UNION ALL SELECT 'fact_payment', payment_id FROM stg_payment GROUP BY 2 HAVING COUNT(*) > 1
UNION ALL SELECT 'fact_attempt', attempt_id FROM stg_attempt GROUP BY 2 HAVING COUNT(*) > 1
UNION ALL SELECT 'fact_attempt(payment_id,attempt_no)', payment_id || '|' || attempt_no
          FROM stg_attempt GROUP BY 2 HAVING COUNT(*) > 1
UNION ALL SELECT 'fact_settlement', settlement_id FROM stg_settlement GROUP BY 2 HAVING COUNT(*) > 1
UNION ALL SELECT 'fact_settlement(payment_id)', payment_id FROM stg_settlement GROUP BY 2 HAVING COUNT(*) > 1;

-- name: c02_fk_valid
-- Test 1 (FK): every foreign key resolves.
SELECT 'payment.merchant_id' AS fk, p.payment_id AS key
FROM stg_payment p ANTI JOIN stg_merchant m USING (merchant_id)
UNION ALL SELECT 'payment.method_code', p.payment_id
FROM stg_payment p ANTI JOIN stg_payment_method m USING (method_code)
UNION ALL SELECT 'attempt.payment_id', a.attempt_id
FROM stg_attempt a ANTI JOIN stg_payment p USING (payment_id)
UNION ALL SELECT 'attempt.acquirer_id', a.attempt_id
FROM stg_attempt a ANTI JOIN stg_acquirer q USING (acquirer_id)
UNION ALL SELECT 'attempt.decline_code', a.attempt_id
FROM stg_attempt a
WHERE a.decline_code IS NOT NULL
  AND a.decline_code NOT IN (SELECT decline_code FROM stg_decline_code)
UNION ALL SELECT 'settlement.payment_id', s.settlement_id
FROM stg_settlement s ANTI JOIN stg_payment p USING (payment_id);

-- name: c03_payment_has_attempt
-- Test 2: every payment has >= 1 attempt.
SELECT p.payment_id FROM stg_payment p ANTI JOIN stg_attempt a USING (payment_id);

-- name: c04_attempt_sequence
-- Tests 2 and 5: attempt_no is 1..n without gaps, n <= 3.
SELECT payment_id, MIN(attempt_no) AS min_no, MAX(attempt_no) AS max_no, COUNT(*) AS n
FROM stg_attempt
GROUP BY payment_id
HAVING MIN(attempt_no) <> 1 OR MAX(attempt_no) <> COUNT(*) OR MAX(attempt_no) > 3;

-- name: c05_attempt_time_order
-- Test 2: timestamps strictly increase with attempt_no; attempt 1 not before payment creation.
WITH seq AS (
    SELECT payment_id, attempt_no, attempted_at_utc,
           LAG(attempted_at_utc) OVER (PARTITION BY payment_id ORDER BY attempt_no) AS prev_at
    FROM stg_attempt
)
SELECT s.payment_id, s.attempt_no
FROM seq s
LEFT JOIN stg_payment p USING (payment_id)
WHERE s.attempted_at_utc <= s.prev_at
   OR (s.attempt_no = 1 AND s.attempted_at_utc < p.created_at_utc);

-- name: c06_approved_is_last
-- Test 3: at most one approved attempt per payment, and it is the last one.
SELECT payment_id
FROM stg_attempt
GROUP BY payment_id
HAVING COUNT(*) FILTER (WHERE result = 'approved') > 1
    OR (COUNT(*) FILTER (WHERE result = 'approved') = 1
        AND MAX(attempt_no) FILTER (WHERE result = 'approved') <> MAX(attempt_no));

-- name: c07_final_status
-- Test 4: final_status = succeeded <=> an approved attempt exists.
WITH a AS (
    SELECT payment_id, BOOL_OR(result = 'approved') AS has_approved
    FROM stg_attempt GROUP BY payment_id
)
SELECT p.payment_id, p.final_status, a.has_approved
FROM stg_payment p
LEFT JOIN a USING (payment_id)
WHERE p.final_status NOT IN ('succeeded', 'failed')
   OR (p.final_status = 'succeeded') <> COALESCE(a.has_approved, FALSE);

-- name: c08_no_retry_after_hard
-- Test 5: no attempt follows a hard decline.
WITH seq AS (
    SELECT a.payment_id, a.attempt_no, d.category,
           LEAD(a.attempt_no) OVER (PARTITION BY a.payment_id ORDER BY a.attempt_no) AS next_no
    FROM stg_attempt a
    LEFT JOIN stg_decline_code d USING (decline_code)
)
SELECT payment_id, attempt_no FROM seq WHERE category = 'hard' AND next_no IS NOT NULL;

-- name: c09_result_code_coherence
-- Test 6: result x decline_code x category coherence.
SELECT a.attempt_id, a.result, a.decline_code, d.category
FROM stg_attempt a
LEFT JOIN stg_decline_code d USING (decline_code)
WHERE a.result NOT IN ('approved', 'declined', 'error')
   OR (a.result = 'approved' AND a.decline_code IS NOT NULL)
   OR (a.result = 'declined' AND COALESCE(d.category, '') NOT IN ('soft', 'hard'))
   OR (a.result = 'error' AND COALESCE(d.category, '') <> 'technical');

-- name: c10_method_acquirer_country
-- Test 7: pix only in BR and only via PIX_BR; acquirer in the merchant's country; method
-- available in that country; payment currency = merchant currency.
SELECT p.payment_id, a.attempt_id, m.country, p.method_code, a.acquirer_id
FROM stg_payment p
JOIN stg_merchant m USING (merchant_id)
LEFT JOIN stg_attempt a USING (payment_id)
LEFT JOIN stg_acquirer q USING (acquirer_id)
LEFT JOIN stg_payment_method pm USING (method_code)
WHERE (p.method_code = 'pix' AND m.country <> 'BR')
   OR ((p.method_code = 'pix') <> (a.acquirer_id = 'PIX_BR'))
   OR q.country <> m.country
   OR NOT list_contains(string_split(pm.available_countries, ','), m.country)
   OR p.currency <> m.currency;

-- name: c11_amount_valid
-- Amount validity: amount > 0; CLP without decimals; non-negative costs; latency > 0.
SELECT 'payment.amount' AS rule, payment_id AS key
FROM stg_payment
WHERE amount <= 0 OR (currency = 'CLP' AND amount <> ROUND(amount, 0))
UNION ALL SELECT 'attempt.cost_latency', attempt_id
FROM stg_attempt
WHERE processing_cost < 0 OR latency_ms <= 0;

-- name: c12_settlement_consistency
-- Test 8: exactly 1 settlement per succeeded payment, none for failed ones;
-- gross = amount; net = gross - fee; same currency.
SELECT 'missing_or_extra' AS rule, p.payment_id AS key
FROM stg_payment p
LEFT JOIN (SELECT payment_id, COUNT(*) AS n FROM stg_settlement GROUP BY 1) s USING (payment_id)
WHERE (p.final_status = 'succeeded' AND COALESCE(s.n, 0) <> 1)
   OR (p.final_status <> 'succeeded' AND COALESCE(s.n, 0) > 0)
UNION ALL
SELECT 'values', s.settlement_id
FROM stg_settlement s
JOIN stg_payment p USING (payment_id)
WHERE s.gross_amount <> p.amount
   OR s.net_amount <> s.gross_amount - s.fee
   OR s.currency <> p.currency;

-- name: c13_fx_and_activation
-- Test 10 support: every payment has a positive FX rate on its local creation date, so any
-- BRL consolidation is possible without summing raw currencies; activation <= payment date.
WITH p AS (
    SELECT p.payment_id, p.currency, m.activation_date,
           CAST(timezone(m.timezone, timezone('UTC', p.created_at_utc)) AS DATE) AS d
    FROM stg_payment p JOIN stg_merchant m USING (merchant_id)
)
SELECT 'fx_missing' AS rule, p.payment_id AS key
FROM p LEFT JOIN stg_fx_rate fx ON fx.currency = p.currency AND fx.rate_date = p.d
WHERE fx.rate_to_brl IS NULL OR fx.rate_to_brl <= 0
UNION ALL
SELECT 'activation_after_payment', payment_id FROM p WHERE d < activation_date;
