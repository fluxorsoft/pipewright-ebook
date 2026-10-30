-- customer_activity: the data team's feature table. One row per active customer per month, with what was true
-- as of midnight (UTC) at the start of that month, computed only from the 365 days before it. feature_timestamp is
-- that moment, so a point-in-time read never sees a value from after a row's cut-off.
--
-- This backfill computes every past month from the data that existed then. After it, the monthly job
-- (customer_activity_month.sql) appends one month at a time; no row is ever updated.
CREATE OR REPLACE TABLE `pw_retail.customer_activity`
PARTITION BY DATE(feature_timestamp)
CLUSTER BY customer_id
AS
WITH months AS (
  SELECT TIMESTAMP(m) AS as_of
  FROM UNNEST(GENERATE_DATE_ARRAY('2010-01-01', '2011-11-01', INTERVAL 1 MONTH)) AS m
),
purchases AS (                                  -- cancellations and returns are not purchases
  SELECT *
  FROM `pw_retail.retail_transactions`
  WHERE NOT STARTS_WITH(invoice, 'C') AND quantity > 0
)
SELECT
  p.customer_id,
  m.as_of                                          AS feature_timestamp,
  TIMESTAMP_DIFF(m.as_of, MAX(p.invoice_date), DAY) AS recency_days,
  COUNT(DISTINCT p.invoice)                        AS orders_12m,
  ROUND(SUM(p.quantity * p.price), 2)              AS spend_12m_gbp,
  COUNT(DISTINCT p.stock_code)                     AS distinct_products,
  -- the customer's rhythm (Chapter 11): average days between their orders in the year, empty with one order
  ROUND(SAFE_DIVIDE(TIMESTAMP_DIFF(MAX(p.invoice_date), MIN(p.invoice_date), SECOND) / 86400,
                    COUNT(DISTINCT p.invoice) - 1), 1)  AS avg_days_between_orders
FROM months AS m
JOIN purchases AS p
  ON  p.invoice_date <  m.as_of
  AND p.invoice_date >= TIMESTAMP_SUB(m.as_of, INTERVAL 365 DAY)
GROUP BY p.customer_id, m.as_of
