-- segment_customers: who is segmented, as of when. Every customer who bought in the 365 days before the 1st of a
-- month, from the data team's feature table; one cut-off per run, the latest month by default.
CREATE OR REPLACE TABLE `pw_retail.segment_customers` AS
SELECT customer_id, DATE(feature_timestamp) AS snapshot_date
FROM `pw_retail.customer_activity`
WHERE feature_timestamp = (SELECT MAX(feature_timestamp) FROM `pw_retail.customer_activity`)
