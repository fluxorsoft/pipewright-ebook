-- lapse_risk_entities: the entity table the lapse model trains from. One row per customer who bought in the 365
-- days before a monthly cut-off: who, as of when, and their main country. No label and no features: Pipewright
-- takes the label from customer_purchases (data.label_source) and the features from customer_activity
-- (data.features_from), each as of the row's cut-off.
--
-- Every month has a row, up to the latest. Rows whose 90-day window has not closed yet are dropped at each run, so
-- the same table serves every run as the months go by.
--
-- Cut-offs start in December 2010, the first with a full year of transactions behind it (they start on
-- 2009-12-01). Earlier cut-offs had features over less than the 365 days they claim: recency could not exceed the
-- months since the data began. Monitoring found it (Chapter 14): the training data's recency was too short, so
-- every 2011 scoring looked drifted.
CREATE OR REPLACE TABLE `pw_retail.lapse_risk_entities`
AS
WITH cutoffs AS (
  SELECT d AS snapshot_date, TIMESTAMP(d) AS cutoff
  FROM UNNEST(GENERATE_DATE_ARRAY('2010-12-01', '2011-12-01', INTERVAL 1 MONTH)) AS d
),
purchases AS (
  SELECT *
  FROM `pw_retail.retail_transactions`
  WHERE NOT STARTS_WITH(invoice, 'C') AND quantity > 0
),
lines_before AS (                               -- invoice lines per country, in the year before each cut-off
  SELECT c.snapshot_date, p.customer_id, p.country, COUNT(*) AS lines
  FROM cutoffs AS c
  JOIN purchases AS p
    ON p.invoice_date < c.cutoff AND p.invoice_date >= TIMESTAMP_SUB(c.cutoff, INTERVAL 365 DAY)
  GROUP BY c.snapshot_date, p.customer_id, p.country
)
SELECT customer_id, snapshot_date,
       ARRAY_AGG(country ORDER BY lines DESC, country LIMIT 1)[OFFSET(0)] AS country
FROM lines_before
GROUP BY snapshot_date, customer_id
