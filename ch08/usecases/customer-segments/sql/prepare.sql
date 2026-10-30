-- Preparation in SQL: one SELECT over {rows}, the run's rows (the customers with their features). Pipewright writes its
-- result into the run's rows before training, runs it again when it scores, and pins the file with the release.
SELECT
  *,
  ROUND(SAFE_DIVIDE(spend_12m_gbp, orders_12m), 2) AS avg_order_gbp    -- what a typical order is worth
FROM {rows}
