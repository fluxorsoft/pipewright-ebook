-- retail_entities: a small entity table for Chapter 20, where a coding agent drafts a new use case from it. One row
-- per customer and monthly cut-off (the same customers and cut-offs as lapse_risk_entities), and a label: churned is
-- 1 when the customer bought nothing in the 90 days after the cut-off, else 0. Only cut-offs whose 90 days have
-- closed by the last purchase in the data are kept. The agent sees this table's schema and row count, never a row.
CREATE OR REPLACE TABLE `pw_retail.retail_entities` AS
WITH last_day AS (SELECT DATE(MAX(purchased_at)) AS d FROM `pw_retail.customer_purchases`)
SELECT e.customer_id, e.snapshot_date,
       IF(COUNTIF(p.purchased_at >= TIMESTAMP(e.snapshot_date)
                  AND p.purchased_at < TIMESTAMP(DATE_ADD(e.snapshot_date, INTERVAL 90 DAY))) > 0, 0, 1) AS churned
FROM `pw_retail.lapse_risk_entities` AS e
CROSS JOIN last_day
LEFT JOIN `pw_retail.customer_purchases` AS p ON p.customer_id = e.customer_id
WHERE DATE_ADD(e.snapshot_date, INTERVAL 90 DAY) <= last_day.d
GROUP BY e.customer_id, e.snapshot_date
