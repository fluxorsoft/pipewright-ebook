-- lapse_risk_entities: the entity table the lapse model trains from. One row per customer who bought in the 365
-- days before a monthly cut-off: who, as of when, their main country, and the label. No features: the model reads
-- those from customer_activity, point in time.
--
-- lapsed is 1 when the customer buys nothing in the 90 days from the cut-off. The last cut-off is 1 September 2011,
-- the last whose 90 days had passed when the data ends (9 December 2011).
CREATE OR REPLACE TABLE `pw_retail.lapse_risk_entities`
AS
WITH cutoffs AS (
  SELECT d AS snapshot_date, TIMESTAMP(d) AS cutoff
  FROM UNNEST(GENERATE_DATE_ARRAY('2010-06-01', '2011-09-01', INTERVAL 1 MONTH)) AS d
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
),
active AS (
  SELECT snapshot_date, customer_id,
         ARRAY_AGG(country ORDER BY lines DESC, country LIMIT 1)[OFFSET(0)] AS country
  FROM lines_before
  GROUP BY snapshot_date, customer_id
),
came_back AS (                                  -- bought again within 90 days of the cut-off
  SELECT DISTINCT c.snapshot_date, p.customer_id
  FROM cutoffs AS c
  JOIN purchases AS p
    ON p.invoice_date >= c.cutoff AND p.invoice_date < TIMESTAMP_ADD(c.cutoff, INTERVAL 90 DAY)
)
SELECT a.customer_id, a.snapshot_date, a.country,
       IF(b.customer_id IS NULL, 1, 0) AS lapsed
FROM active AS a
LEFT JOIN came_back AS b USING (snapshot_date, customer_id)
