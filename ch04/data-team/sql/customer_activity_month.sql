-- customer_activity, the monthly job: appends the month that starts at @as_of (a TIMESTAMP, midnight UTC on the
-- 1st). Run it once, early on the 1st:
--   bq query --use_legacy_sql=false --parameter=as_of:TIMESTAMP:"2011-12-01 00:00:00" < customer_activity_month.sql
-- It refuses a month that is already there, so a repeated run never adds a second row per customer.
ASSERT NOT EXISTS (SELECT 1 FROM `pw_retail.customer_activity` WHERE feature_timestamp = @as_of)
  AS 'customer_activity already has this month';

INSERT INTO `pw_retail.customer_activity`
  (customer_id, feature_timestamp, recency_days, orders_12m, spend_12m_gbp, distinct_products)
SELECT
  customer_id,
  @as_of,
  TIMESTAMP_DIFF(@as_of, MAX(invoice_date), DAY),
  COUNT(DISTINCT invoice),
  ROUND(SUM(quantity * price), 2),
  COUNT(DISTINCT stock_code)
FROM `pw_retail.retail_transactions`
WHERE NOT STARTS_WITH(invoice, 'C') AND quantity > 0
  AND invoice_date <  @as_of
  AND invoice_date >= TIMESTAMP_SUB(@as_of, INTERVAL 365 DAY)
GROUP BY customer_id;
