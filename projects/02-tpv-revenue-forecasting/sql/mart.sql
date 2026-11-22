-- P2 forecasting mart (data_origin: derived + synthetic adjustments). Runs on top of the P1 core
-- tables (fct_payment, stg_settlement, dim_merchant) built by fintech_lab.p1_payments.warehouse.
-- Placeholders {win_start}, {win_end}, {incentive_rate}, {var_cost_rate} are filled by mart.py.
-- All money is BRL, DECIMAL(18,4). Rounding happens ONCE at the lowest grain (merchant x method x
-- day); every upper table only SUMs components, so daily/monthly/merchant/total reconcile exactly.

-- name: p2_payment_fin
-- grain: 1 succeeded payment. TPV by payment (never by attempt); fee at the payment's local-date FX.
CREATE OR REPLACE TABLE p2_payment_fin AS
SELECT p.payment_id, p.merchant_id, p.method_code, p.country, p.size_tier,
       p.created_date_local AS date_local,
       CAST(p.amount_brl AS DECIMAL(18, 4))                       AS tpv_brl,
       CAST(s.fee * p.rate_to_brl AS DECIMAL(18, 4))              AS fee_brl
FROM fct_payment AS p
JOIN stg_settlement AS s USING (payment_id)
WHERE p.is_succeeded
  AND p.created_date_local BETWEEN DATE '{win_start}' AND DATE '{win_end}';

-- name: p2_mm_pay
-- grain: local date x merchant x method (payments created that day; cost on creation date, like P1).
CREATE OR REPLACE TABLE p2_mm_pay AS
SELECT p.created_date_local AS date_local, p.merchant_id, p.method_code,
       COUNT(*)                                          AS n_payments,
       COUNT(*) FILTER (WHERE p.is_succeeded)            AS n_succeeded,
       CAST(COALESCE(SUM(p.processing_cost_brl), 0) AS DECIMAL(18, 4)) AS proc_cost_brl
FROM fct_payment AS p
WHERE p.created_date_local BETWEEN DATE '{win_start}' AND DATE '{win_end}'
GROUP BY ALL;

-- name: p2_mm_day
-- grain: local date x merchant x method. Payment-day components + adjustment events on EVENT date.
CREATE OR REPLACE TABLE p2_mm_day AS
WITH pay AS (
    SELECT date_local, merchant_id, method_code,
           SUM(tpv_brl) AS tpv_brl, SUM(fee_brl) AS fee_brl
    FROM p2_payment_fin GROUP BY ALL
),
ev AS (
    SELECT event_date_local AS date_local, merchant_id, method_code,
           SUM(CAST(amount_brl AS DECIMAL(18, 4))) FILTER (WHERE event_type = 'refund')
               AS refund_brl,
           SUM(CAST(fee_returned_brl AS DECIMAL(18, 4))) FILTER (WHERE event_type = 'refund')
               AS refund_fee_returned_brl,
           SUM(CAST(amount_brl + chargeback_fee_brl AS DECIMAL(18, 4)))
               FILTER (WHERE event_type = 'chargeback') AS chargeback_brl
    FROM syn_adjustment
    WHERE event_date_local BETWEEN DATE '{win_start}' AND DATE '{win_end}'
    GROUP BY ALL
),
keys AS (
    SELECT date_local, merchant_id, method_code FROM p2_mm_pay
    UNION SELECT date_local, merchant_id, method_code FROM pay
    UNION SELECT date_local, merchant_id, method_code FROM ev
)
SELECT k.date_local, k.merchant_id, k.method_code,
       COALESCE(m.n_payments, 0)  AS n_payments,
       COALESCE(m.n_succeeded, 0) AS n_succeeded,
       COALESCE(pay.tpv_brl, 0)   AS tpv_brl,
       COALESCE(pay.fee_brl, 0)   AS fee_brl,
       COALESCE(m.proc_cost_brl, 0)               AS proc_cost_brl,
       COALESCE(ev.refund_brl, 0)                 AS refund_brl,
       COALESCE(ev.refund_fee_returned_brl, 0)    AS refund_fee_returned_brl,
       COALESCE(ev.chargeback_brl, 0)             AS chargeback_brl,
       CAST(COALESCE(pay.tpv_brl, 0) * {incentive_rate} AS DECIMAL(18, 4)) AS incentive_brl,
       CAST(COALESCE(pay.tpv_brl, 0) * {var_cost_rate}  AS DECIMAL(18, 4)) AS var_cost_brl
FROM keys AS k
LEFT JOIN p2_mm_pay AS m USING (date_local, merchant_id, method_code)
LEFT JOIN pay USING (date_local, merchant_id, method_code)
LEFT JOIN ev  USING (date_local, merchant_id, method_code);

-- name: fct_daily_merchant
-- grain: local date x merchant, from max(activation, window start). Zero rows after activation are
-- explicit; days before activation do not exist (absent, not zero).
CREATE OR REPLACE TABLE fct_daily_merchant AS
WITH spine AS (
    SELECT m.merchant_id, CAST(d AS DATE) AS date_local
    FROM dim_merchant AS m,
         generate_series(GREATEST(m.activation_date, DATE '{win_start}'),
                         DATE '{win_end}', INTERVAL 1 DAY) AS t(d)
),
a AS (
    SELECT date_local, merchant_id,
           SUM(n_payments) AS n_payments, SUM(n_succeeded) AS n_succeeded,
           SUM(tpv_brl) AS tpv_brl, SUM(fee_brl) AS fee_brl, SUM(proc_cost_brl) AS proc_cost_brl,
           SUM(refund_brl) AS refund_brl, SUM(refund_fee_returned_brl) AS refund_fee_returned_brl,
           SUM(chargeback_brl) AS chargeback_brl, SUM(incentive_brl) AS incentive_brl,
           SUM(var_cost_brl) AS var_cost_brl
    FROM p2_mm_day GROUP BY ALL
)
SELECT s.date_local, s.merchant_id, m.country, m.size_tier,
       COALESCE(a.n_payments, 0) AS n_payments, COALESCE(a.n_succeeded, 0) AS n_succeeded,
       COALESCE(a.tpv_brl, 0) AS tpv_brl, COALESCE(a.fee_brl, 0) AS fee_brl,
       COALESCE(a.proc_cost_brl, 0) AS proc_cost_brl, COALESCE(a.refund_brl, 0) AS refund_brl,
       COALESCE(a.refund_fee_returned_brl, 0) AS refund_fee_returned_brl,
       COALESCE(a.chargeback_brl, 0) AS chargeback_brl,
       COALESCE(a.incentive_brl, 0) AS incentive_brl, COALESCE(a.var_cost_brl, 0) AS var_cost_brl
FROM spine AS s
JOIN dim_merchant AS m USING (merchant_id)
LEFT JOIN a USING (date_local, merchant_id);

-- name: fct_daily_segment
-- grain: local date x country x method x size tier (full date spine; zeros explicit).
CREATE OR REPLACE TABLE fct_daily_segment AS
WITH combos AS (
    SELECT DISTINCT m.country, d.method_code, m.size_tier
    FROM p2_mm_day AS d JOIN dim_merchant AS m USING (merchant_id)
),
spine AS (
    SELECT CAST(t.d AS DATE) AS date_local, c.*
    FROM combos AS c,
         generate_series(DATE '{win_start}', DATE '{win_end}', INTERVAL 1 DAY) AS t(d)
),
a AS (
    SELECT d.date_local, m.country, d.method_code, m.size_tier,
           SUM(n_payments) AS n_payments, SUM(n_succeeded) AS n_succeeded,
           SUM(tpv_brl) AS tpv_brl, SUM(fee_brl) AS fee_brl, SUM(proc_cost_brl) AS proc_cost_brl,
           SUM(refund_brl) AS refund_brl, SUM(refund_fee_returned_brl) AS refund_fee_returned_brl,
           SUM(chargeback_brl) AS chargeback_brl, SUM(incentive_brl) AS incentive_brl,
           SUM(var_cost_brl) AS var_cost_brl
    FROM p2_mm_day AS d JOIN dim_merchant AS m USING (merchant_id)
    GROUP BY ALL
)
SELECT s.date_local, s.country, s.method_code, s.size_tier,
       COALESCE(a.n_payments, 0) AS n_payments, COALESCE(a.n_succeeded, 0) AS n_succeeded,
       COALESCE(a.tpv_brl, 0) AS tpv_brl, COALESCE(a.fee_brl, 0) AS fee_brl,
       COALESCE(a.proc_cost_brl, 0) AS proc_cost_brl, COALESCE(a.refund_brl, 0) AS refund_brl,
       COALESCE(a.refund_fee_returned_brl, 0) AS refund_fee_returned_brl,
       COALESCE(a.chargeback_brl, 0) AS chargeback_brl,
       COALESCE(a.incentive_brl, 0) AS incentive_brl, COALESCE(a.var_cost_brl, 0) AS var_cost_brl
FROM spine AS s
LEFT JOIN a USING (date_local, country, method_code, size_tier);

-- name: fct_daily_total
-- grain: local date. Derived metrics are formulas over summed components (contract F08, F11).
CREATE OR REPLACE TABLE fct_daily_total AS
WITH t AS (
    SELECT date_local, COUNT(*) AS active_merchants,
           SUM(n_payments) AS n_payments, SUM(n_succeeded) AS n_succeeded,
           SUM(tpv_brl) AS tpv_brl, SUM(fee_brl) AS fee_brl, SUM(proc_cost_brl) AS proc_cost_brl,
           SUM(refund_brl) AS refund_brl, SUM(refund_fee_returned_brl) AS refund_fee_returned_brl,
           SUM(chargeback_brl) AS chargeback_brl, SUM(incentive_brl) AS incentive_brl,
           SUM(var_cost_brl) AS var_cost_brl
    FROM fct_daily_merchant GROUP BY ALL
)
SELECT t.*,
       fee_brl - refund_fee_returned_brl - chargeback_brl - incentive_brl AS net_revenue_brl,
       fee_brl - refund_fee_returned_brl - chargeback_brl - incentive_brl
           - proc_cost_brl - var_cost_brl AS contribution_brl,
       fee_brl / NULLIF(tpv_brl, 0) AS take_rate
FROM t;

-- name: fct_monthly
-- grain: local month x country.
CREATE OR REPLACE TABLE fct_monthly AS
WITH t AS (
    SELECT CAST(date_trunc('month', date_local) AS DATE) AS month, country,
           SUM(n_payments) AS n_payments, SUM(n_succeeded) AS n_succeeded,
           SUM(tpv_brl) AS tpv_brl, SUM(fee_brl) AS fee_brl, SUM(proc_cost_brl) AS proc_cost_brl,
           SUM(refund_brl) AS refund_brl, SUM(refund_fee_returned_brl) AS refund_fee_returned_brl,
           SUM(chargeback_brl) AS chargeback_brl, SUM(incentive_brl) AS incentive_brl,
           SUM(var_cost_brl) AS var_cost_brl
    FROM fct_daily_merchant GROUP BY ALL
)
SELECT t.*,
       fee_brl - refund_fee_returned_brl - chargeback_brl - incentive_brl AS net_revenue_brl,
       fee_brl - refund_fee_returned_brl - chargeback_brl - incentive_brl
           - proc_cost_brl - var_cost_brl AS contribution_brl,
       fee_brl / NULLIF(tpv_brl, 0) AS take_rate
FROM t;
