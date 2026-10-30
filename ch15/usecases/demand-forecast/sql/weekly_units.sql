-- weekly_product_units: units sold per week of the ten products in the most orders, cancellations and returns left
-- out. Every product has every week, zero when nothing sold, so each series has no gaps. The last week is left out:
-- the data ends on a Friday (9 December 2011), and a part week would look like a collapse in demand.
CREATE OR REPLACE TABLE `pw_retail.weekly_product_units` AS
WITH lines AS (
  SELECT customer_id, stock_code, ABS(quantity) AS quantity, STARTS_WITH(invoice, 'C') AS cancelled, invoice,
         DATE_TRUNC(DATE(invoice_date), WEEK(MONDAY)) AS week_start
  FROM `pw_retail.retail_transactions`
  WHERE REGEXP_CONTAINS(stock_code, r'^[0-9]')          -- products, not postage, fees or manual adjustments
),
purchases AS (                                          -- a purchase a cancellation of the same size reversed is no sale
  SELECT p.stock_code, p.week_start, p.quantity, p.invoice
  FROM lines AS p
  WHERE NOT p.cancelled AND NOT EXISTS (
    SELECT 1 FROM lines AS c
    WHERE c.cancelled AND c.customer_id = p.customer_id AND c.stock_code = p.stock_code AND c.quantity = p.quantity)
),
top10 AS (                                              -- by how many orders, so one bulk order cannot make the list
  SELECT stock_code FROM purchases
  WHERE stock_code != '47566'   -- party bunting: out of stock in July and August 2010, so its sales there are not its
                                -- demand; left out until the stock-out weeks are handled (Chapter 8)
  GROUP BY stock_code ORDER BY COUNT(DISTINCT invoice) DESC LIMIT 10
),
weeks AS (
  SELECT w AS week_start
  FROM UNNEST(GENERATE_DATE_ARRAY('2009-11-30', '2011-11-28', INTERVAL 1 WEEK)) AS w
)
SELECT t.stock_code, w.week_start, COALESCE(SUM(p.quantity), 0) AS units
FROM top10 AS t CROSS JOIN weeks AS w
LEFT JOIN purchases AS p USING (stock_code, week_start)
GROUP BY t.stock_code, w.week_start
