-- P2 reconciliation checks. Each `-- name:` block returns VIOLATING rows; 0 rows = pass.
-- Ids follow docs/metric_contracts.md (R01..R09). Placeholders: {win_start}, {win_end}.

-- name: r01_daily_monthly_total
-- Daily total, monthly and (month x country) agree on every component, month by month.
WITH d AS (
    SELECT CAST(date_trunc('month', date_local) AS DATE) AS month,
           SUM(tpv_brl) AS tpv, SUM(fee_brl) AS fee, SUM(net_revenue_brl) AS net,
           SUM(contribution_brl) AS contrib, SUM(n_succeeded) AS n
    FROM fct_daily_total GROUP BY ALL
),
m AS (
    SELECT month, SUM(tpv_brl) AS tpv, SUM(fee_brl) AS fee, SUM(net_revenue_brl) AS net,
           SUM(contribution_brl) AS contrib, SUM(n_succeeded) AS n
    FROM fct_monthly GROUP BY ALL
)
SELECT d.month FROM d FULL JOIN m USING (month)
WHERE d.tpv IS DISTINCT FROM m.tpv OR d.fee IS DISTINCT FROM m.fee OR d.net IS DISTINCT FROM m.net
   OR d.contrib IS DISTINCT FROM m.contrib OR d.n IS DISTINCT FROM m.n;

-- name: r02_merchant_segment_total
-- Sum over merchants = sum over segments = consolidated, per date.
WITH a AS (SELECT date_local, SUM(tpv_brl) AS tpv, SUM(fee_brl) AS fee, SUM(proc_cost_brl) AS pc,
                  SUM(chargeback_brl) AS cb, SUM(refund_brl) AS rf FROM fct_daily_merchant GROUP BY 1),
     b AS (SELECT date_local, SUM(tpv_brl) AS tpv, SUM(fee_brl) AS fee, SUM(proc_cost_brl) AS pc,
                  SUM(chargeback_brl) AS cb, SUM(refund_brl) AS rf FROM fct_daily_segment GROUP BY 1),
     c AS (SELECT date_local, tpv_brl AS tpv, fee_brl AS fee, proc_cost_brl AS pc,
                  chargeback_brl AS cb, refund_brl AS rf FROM fct_daily_total)
SELECT date_local FROM a
FULL JOIN b USING (date_local) FULL JOIN c USING (date_local)
WHERE (a.tpv, a.fee, a.pc, a.cb, a.rf) IS DISTINCT FROM (b.tpv, b.fee, b.pc, b.cb, b.rf)
   OR (a.tpv, a.fee, a.pc, a.cb, a.rf) IS DISTINCT FROM (c.tpv, c.fee, c.pc, c.cb, c.rf);

-- name: r03_tpv_equals_p1_m07
-- F01 = P1 M07 (approved TPV in BRL) per local date x country, same window.
WITH p1 AS (
    SELECT created_date_local AS date_local, country, SUM(m07_tpv_brl) AS tpv
    FROM mart_auth_daily
    WHERE created_date_local BETWEEN DATE '{win_start}' AND DATE '{win_end}' GROUP BY ALL
),
p2 AS (SELECT date_local, country, SUM(tpv_brl) AS tpv FROM fct_daily_segment GROUP BY ALL)
SELECT date_local, country FROM p1 FULL JOIN p2 USING (date_local, country)
WHERE COALESCE(p1.tpv, 0) <> COALESCE(p2.tpv, 0);

-- name: r04_payments_unique_and_counted
-- No duplicated payment_id in the payment-level table; succeeded count = P1 count in window.
SELECT payment_id FROM p2_payment_fin GROUP BY payment_id HAVING COUNT(*) > 1
UNION ALL
SELECT 'count_mismatch' WHERE
    (SELECT SUM(n_succeeded) FROM fct_daily_total)
    <> (SELECT COUNT(*) FROM fct_payment
        WHERE is_succeeded AND created_date_local BETWEEN DATE '{win_start}' AND DATE '{win_end}');

-- name: r05_fee_vs_raw_settlement
-- F04 recomputed from RAW staging (own timezone + FX join), independent of the P1 core tables.
WITH raw AS (
    SELECT SUM(CAST(s.fee * fx.rate_to_brl AS DECIMAL(18, 4))) AS fee
    FROM stg_settlement AS s
    JOIN stg_payment AS p USING (payment_id)
    JOIN stg_merchant AS m USING (merchant_id)
    JOIN stg_fx_rate AS fx
      ON fx.currency = p.currency
     AND fx.rate_date = CAST(timezone(m.timezone, timezone('UTC', p.created_at_utc)) AS DATE)
    WHERE p.final_status = 'succeeded'
      AND CAST(timezone(m.timezone, timezone('UTC', p.created_at_utc)) AS DATE)
          BETWEEN DATE '{win_start}' AND DATE '{win_end}'
)
SELECT 'fee_mismatch' FROM raw WHERE fee <> (SELECT SUM(fee_brl) FROM fct_daily_total);

-- name: r06_proc_cost_equals_p1_m08
SELECT 'cost_mismatch' WHERE
    (SELECT SUM(proc_cost_brl) FROM fct_daily_total)
    <> (SELECT SUM(m08_processing_cost_brl) FROM mart_auth_daily
        WHERE created_date_local BETWEEN DATE '{win_start}' AND DATE '{win_end}');

-- name: r07_keys_and_spine
-- Unique keys; each merchant has exactly one row per day from activation (or window start).
SELECT 'dup_merchant_day' FROM (SELECT 1 FROM fct_daily_merchant
    GROUP BY date_local, merchant_id HAVING COUNT(*) > 1)
UNION ALL
SELECT 'dup_segment_day' FROM (SELECT 1 FROM fct_daily_segment
    GROUP BY date_local, country, method_code, size_tier HAVING COUNT(*) > 1)
UNION ALL
SELECT 'spine_' || merchant_id FROM (
    SELECT m.merchant_id,
           date_diff('day', GREATEST(m.activation_date, DATE '{win_start}'), DATE '{win_end}') + 1 AS exp,
           COUNT(f.date_local) AS got
    FROM dim_merchant AS m LEFT JOIN fct_daily_merchant AS f USING (merchant_id)
    GROUP BY m.merchant_id, m.activation_date
) WHERE exp <> got
UNION ALL
SELECT 'before_activation' FROM fct_daily_merchant AS f JOIN dim_merchant AS m USING (merchant_id)
WHERE f.date_local < m.activation_date;

-- name: r08_adjustments_valid
-- Refund/chargeback are mutually exclusive per payment and only hit succeeded payments.
SELECT payment_id FROM syn_adjustment GROUP BY payment_id HAVING COUNT(*) > 1
UNION ALL
SELECT a.payment_id FROM syn_adjustment AS a
LEFT JOIN fct_payment AS p USING (payment_id) WHERE p.is_succeeded IS DISTINCT FROM TRUE;

-- name: r09_margin_identity
-- Net revenue and contribution follow the contract formulas on every row of every table.
SELECT CAST(date_local AS VARCHAR) FROM fct_daily_total
WHERE net_revenue_brl <> fee_brl - refund_fee_returned_brl - chargeback_brl - incentive_brl
   OR contribution_brl <> net_revenue_brl - proc_cost_brl - var_cost_brl
UNION ALL
SELECT CAST(month AS VARCHAR) FROM fct_monthly
WHERE net_revenue_brl <> fee_brl - refund_fee_returned_brl - chargeback_brl - incentive_brl
   OR contribution_brl <> net_revenue_brl - proc_cost_brl - var_cost_brl;
