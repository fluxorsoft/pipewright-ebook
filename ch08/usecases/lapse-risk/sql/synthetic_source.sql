-- The rows the synthetic copy learns from: exactly what one training run read (its snapshot, Chapter 5), keyed
-- and labelled. Pipewright joins the features point in time, as for training. Change the run_id to learn from
-- another run.
CREATE OR REPLACE VIEW `pw_retail.lapse_risk_synthetic_source` AS
SELECT customer_id, snapshot_date, country, returned
FROM `pw_retail.lapse_risk_snapshots`
WHERE run_id = 'rbcb69cdc615a'
