-- lapse_risk_scoring: who is scored this week. The customers active at the latest cut-off, as of that cut-off; the
-- scoring pipeline joins their features point in time, exactly as training did. No label: nobody knows yet.
CREATE OR REPLACE VIEW `pw_retail.lapse_risk_scoring` AS
SELECT customer_id, snapshot_date, country
FROM `pw_retail.lapse_risk_entities`
WHERE snapshot_date = (SELECT MAX(snapshot_date) FROM `pw_retail.lapse_risk_entities`)
