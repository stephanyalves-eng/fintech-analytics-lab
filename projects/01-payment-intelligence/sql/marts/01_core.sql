-- Core layer: dimensions, payment-grain and attempt-grain facts (data_origin = derived).
-- Local time = merchant timezone; FX = rate of the payment's LOCAL creation date (metric catalog).

CREATE OR REPLACE TABLE dim_merchant AS SELECT * FROM stg_merchant;
CREATE OR REPLACE TABLE dim_acquirer AS SELECT * FROM stg_acquirer;
CREATE OR REPLACE TABLE dim_payment_method AS SELECT * FROM stg_payment_method;
CREATE OR REPLACE TABLE dim_decline_code AS SELECT * FROM stg_decline_code;
CREATE OR REPLACE TABLE dim_fx_rate AS SELECT * FROM stg_fx_rate;

-- int_payment · grain: 1 payment. Defensive dedup on payment_id (ROW_NUMBER) so a
-- duplicated source row can never fan out downstream joins.
CREATE OR REPLACE TABLE int_payment AS
WITH dedup AS (
    SELECT *
    FROM stg_payment
    QUALIFY ROW_NUMBER() OVER (PARTITION BY payment_id ORDER BY created_at_utc, merchant_id) = 1
),
localized AS (
    SELECT p.*, m.country, m.sector, m.size_tier, m.timezone, m.activation_date,
           timezone(m.timezone, timezone('UTC', p.created_at_utc)) AS created_at_local
    FROM dedup AS p
    JOIN stg_merchant AS m USING (merchant_id)
)
SELECT l.*,
       CAST(l.created_at_local AS DATE)               AS created_date_local,
       CAST(date_trunc('month', l.created_at_local) AS DATE) AS created_month_local,
       hour(l.created_at_local)                       AS created_hour_local,
       fx.rate_to_brl,
       CAST(l.amount * fx.rate_to_brl AS DECIMAL(18, 2)) AS amount_brl,
       CASE
           WHEN l.amount * fx.rate_to_brl < 50   THEN '1: <50'
           WHEN l.amount * fx.rate_to_brl < 200  THEN '2: 50-200'
           WHEN l.amount * fx.rate_to_brl < 1000 THEN '3: 200-1000'
           ELSE '4: >=1000'
       END AS amount_band_brl
FROM localized AS l
LEFT JOIN stg_fx_rate AS fx
       ON fx.currency = l.currency AND fx.rate_date = CAST(l.created_at_local AS DATE);

-- fct_attempt · grain: 1 authorization attempt, with retry-sequencing features.
CREATE OR REPLACE TABLE fct_attempt AS
WITH base AS (
    SELECT a.*,
           p.merchant_id, p.method_code, p.currency, p.country, p.sector, p.size_tier,
           p.created_date_local, p.created_month_local, p.amount_band_brl, p.rate_to_brl,
           timezone(p.timezone, timezone('UTC', a.attempted_at_utc)) AS attempted_at_local,
           d.category     AS decline_category,
           d.reason_group AS reason_group
    FROM stg_attempt AS a
    JOIN int_payment AS p USING (payment_id)
    LEFT JOIN stg_decline_code AS d USING (decline_code)
)
SELECT base.*,
       hour(attempted_at_local)                                   AS attempted_hour_local,
       CAST(processing_cost * rate_to_brl AS DECIMAL(18, 4))      AS processing_cost_brl,
       LAG(result)           OVER w                               AS prev_result,
       LAG(decline_category) OVER w                               AS prev_category,
       LAG(acquirer_id)      OVER w                               AS prev_acquirer_id,
       acquirer_id <> LAG(acquirer_id) OVER w                     AS switched_acquirer,
       date_diff('millisecond', LAG(attempted_at_utc) OVER w, attempted_at_utc) / 1000.0
                                                                  AS seconds_since_prev,
       LEAD(result)          OVER w                               AS next_result,
       ROW_NUMBER() OVER (PARTITION BY payment_id ORDER BY attempt_no DESC) = 1
                                                                  AS is_last_attempt
FROM base
WINDOW w AS (PARTITION BY payment_id ORDER BY attempt_no);

-- fct_payment · grain: 1 payment. Attempts are pre-aggregated per payment BEFORE the join,
-- so payment amounts are never repeated per attempt (anti double counting, test 9).
CREATE OR REPLACE TABLE fct_payment AS
WITH att AS (
    SELECT payment_id,
           COUNT(*)                                         AS n_attempts,
           COUNT(*) FILTER (WHERE result = 'approved')      AS n_approved,
           COUNT(*) FILTER (WHERE result = 'error')         AS n_error,
           COUNT(*) FILTER (WHERE decline_category = 'soft') AS n_soft,
           COUNT(*) FILTER (WHERE decline_category = 'hard') AS n_hard,
           SUM(processing_cost)                             AS processing_cost,
           SUM(processing_cost_brl)                         AS processing_cost_brl,
           first(acquirer_id ORDER BY attempt_no)           AS first_acquirer_id,
           last(acquirer_id ORDER BY attempt_no)            AS last_acquirer_id,
           first(result ORDER BY attempt_no)                AS first_result,
           first(decline_category ORDER BY attempt_no)      AS first_category,
           MAX(attempt_no)                                  AS last_attempt_no
    FROM fct_attempt
    GROUP BY payment_id
)
SELECT p.*,
       COALESCE(att.n_attempts, 0) AS n_attempts,
       att.* EXCLUDE (payment_id, n_attempts),
       p.final_status = 'succeeded'                                     AS is_succeeded,
       p.final_status = 'succeeded' AND att.last_attempt_no > 1         AS recovered_by_retry,
       att.first_category IN ('soft', 'technical')                      AS first_failed_retryable
FROM int_payment AS p
LEFT JOIN att USING (payment_id);
