-- The TRANSFORM clause: BigQuery ML applies these expressions inside the model, when it trains, in ML.PREDICT and at a
-- Model Registry endpoint, so the tables keep the real values (and the data contract checks those).
--
-- Spend, orders and product counts have long tails: a few customers spend a hundred times what most do. On the raw
-- values k-means spends its segments on those few. On a log scale, from 200 to 2,000 counts as much as from 2,000 to
-- 20,000, so the segments describe the many.
LN(1 + recency_days)  AS recency_days,
LN(orders_12m)        AS orders_12m,
LN(1 + spend_12m_gbp) AS spend_12m_gbp,
LN(distinct_products) AS distinct_products
