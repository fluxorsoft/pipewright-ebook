-- customer_purchases: the label events. One row per purchase (an invoice that is not a cancellation), with when it
-- happened. The lapse model's label is whether a customer has one of these within 90 days of a cut-off.
--
-- @loaded_until (a TIMESTAMP) is how far the nightly load has got: purchases from then on have not arrived yet.
-- The book uses it to replay a month earlier; the real job loads everything there is.
CREATE OR REPLACE TABLE `pw_retail.customer_purchases`
PARTITION BY DATE(purchased_at)
CLUSTER BY customer_id
AS
SELECT customer_id, invoice, MIN(invoice_date) AS purchased_at
FROM `pw_retail.retail_transactions`
WHERE NOT STARTS_WITH(invoice, 'C') AND quantity > 0
  AND invoice_date < @loaded_until
GROUP BY customer_id, invoice
