-- The weekly scoring as it would have run on the first of each month since June 2011: one view per cut-off,
-- lapse_risk_scoring_2011_06 to lapse_risk_scoring_2011_12, each the customers active at that cut-off, as of it.
-- Scoring each in turn replays seven months of monitoring in an afternoon (Chapter 14).
FOR m IN (SELECT DISTINCT snapshot_date FROM `pw_retail.lapse_risk_entities`
          WHERE snapshot_date >= DATE '2011-06-01' ORDER BY snapshot_date) DO
  EXECUTE IMMEDIATE FORMAT("""
    CREATE OR REPLACE VIEW `pw_retail.lapse_risk_scoring_%s` AS
    SELECT customer_id, snapshot_date, country
    FROM `pw_retail.lapse_risk_entities`
    WHERE snapshot_date = DATE '%t'""", FORMAT_DATE('%Y_%m', m.snapshot_date), m.snapshot_date);
END FOR;
