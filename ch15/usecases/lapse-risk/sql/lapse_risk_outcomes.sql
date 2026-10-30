-- lapse_risk_outcomes: what actually happened to the customers scored on a cut-off whose 90-day window has closed.
-- returned is 1 when the customer bought at or after the cut-off and before cut-off + 90 days, exactly the label the
-- model was trained on (data.label_source in config/data.yaml). The monitoring step joins it to the scores by
-- customer_id and measures the model on it (monitoring.performance, Chapter 14).
--
-- The cut-off is the latest whose window has closed by the time the purchases were loaded: 2011-09-01, as the
-- purchases end on 2011-12-09. In daily use the data team moves it on as each window closes.
CREATE OR REPLACE VIEW `pw_retail.lapse_risk_outcomes` AS
SELECT
  e.customer_id,
  e.snapshot_date AS scored_for,
  IF(COUNT(p.invoice) > 0, 1, 0) AS returned
FROM `pw_retail.lapse_risk_entities` AS e
LEFT JOIN `pw_retail.customer_purchases` AS p
  ON p.customer_id = e.customer_id
 AND p.purchased_at >= TIMESTAMP(e.snapshot_date)
 AND p.purchased_at <  TIMESTAMP(DATE_ADD(e.snapshot_date, INTERVAL 90 DAY))
WHERE e.snapshot_date = DATE '2011-09-01'
GROUP BY e.customer_id, e.snapshot_date
