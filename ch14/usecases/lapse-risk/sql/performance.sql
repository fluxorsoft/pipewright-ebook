-- performance: how well each scoring run ranked the customers whose outcomes are now known (Chapter 14).
-- Each score is joined to the outcome of the cut-off it was made for (scored_for), never to a later or earlier one.
-- AUC by the rank-sum formula: the chance that a customer who came back was scored higher than one who did not.
WITH joined AS (
  SELECT s.run_id, s.model_version_id, s.scored_for, s.return_probability AS p, o.returned AS y
  FROM `pw_retail.lapse_risk_scores` AS s
  JOIN `pw_retail.lapse_risk_outcomes` AS o
    ON o.customer_id = s.customer_id AND o.scored_for = s.scored_for
),
ranked AS (
  SELECT *, RANK() OVER (PARTITION BY run_id ORDER BY p) AS r FROM joined
)
SELECT
  run_id, model_version_id, scored_for,
  COUNT(*) AS customers,
  ROUND(AVG(y), 3) AS came_back,
  ROUND(AVG(p), 3) AS predicted,
  ROUND((SUM(IF(y = 1, r, 0)) - COUNTIF(y = 1) * (COUNTIF(y = 1) + 1) / 2)
        / (COUNTIF(y = 1) * COUNTIF(y = 0)), 4) AS auc
FROM ranked
GROUP BY run_id, model_version_id, scored_for
ORDER BY scored_for, run_id
