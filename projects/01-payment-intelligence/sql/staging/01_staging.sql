-- Staging: 1:1 views over the synthetic Parquet files (data_origin = synthetic).
-- Only typing/renaming here; no joins, so row counts equal the source files.
-- {data_dir} is substituted by fintech_lab.p1_payments.warehouse.

CREATE OR REPLACE VIEW stg_merchant AS
SELECT merchant_id, sector, country, currency, timezone, size_tier,
       CAST(activation_date AS DATE) AS activation_date
FROM read_parquet('{data_dir}/dim_merchant.parquet');

CREATE OR REPLACE VIEW stg_acquirer AS
SELECT acquirer_id, country, acquirer_type,
       CAST(fee_fixed_local AS DECIMAL(18, 2)) AS fee_fixed_local,
       CAST(fee_bps_approved AS INTEGER) AS fee_bps_approved
FROM read_parquet('{data_dir}/dim_acquirer.parquet');

CREATE OR REPLACE VIEW stg_payment_method AS
SELECT method_code, method_family, available_countries,
       CAST(settlement_lag_days AS INTEGER) AS settlement_lag_days
FROM read_parquet('{data_dir}/dim_payment_method.parquet');

CREATE OR REPLACE VIEW stg_decline_code AS
SELECT decline_code, category, reason_group, CAST(retryable AS BOOLEAN) AS retryable
FROM read_parquet('{data_dir}/dim_decline_code.parquet');

CREATE OR REPLACE VIEW stg_fx_rate AS
SELECT CAST(rate_date AS DATE) AS rate_date, currency,
       CAST(rate_to_brl AS DECIMAL(18, 8)) AS rate_to_brl
FROM read_parquet('{data_dir}/dim_fx_rate.parquet');

CREATE OR REPLACE VIEW stg_payment AS
SELECT payment_id, merchant_id, method_code,
       CAST(created_at_utc AS TIMESTAMP) AS created_at_utc,
       CAST(amount AS DECIMAL(18, 2)) AS amount,
       currency, device_type, final_status
FROM read_parquet('{data_dir}/fact_payment.parquet');

CREATE OR REPLACE VIEW stg_attempt AS
SELECT attempt_id, payment_id, CAST(attempt_no AS INTEGER) AS attempt_no, acquirer_id,
       CAST(attempted_at_utc AS TIMESTAMP) AS attempted_at_utc,
       result, decline_code, CAST(latency_ms AS INTEGER) AS latency_ms,
       CAST(processing_cost AS DECIMAL(18, 2)) AS processing_cost
FROM read_parquet('{data_dir}/fact_attempt.parquet');

CREATE OR REPLACE VIEW stg_settlement AS
SELECT settlement_id, payment_id, CAST(settlement_date AS DATE) AS settlement_date,
       CAST(gross_amount AS DECIMAL(18, 2)) AS gross_amount,
       CAST(fee AS DECIMAL(18, 2)) AS fee,
       CAST(net_amount AS DECIMAL(18, 2)) AS net_amount,
       currency
FROM read_parquet('{data_dir}/fact_settlement.parquet');
