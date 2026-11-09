"""The retailer's transactions as the data team would load them into BigQuery: one row per invoice line.

    pip install pandas openpyxl
    python tools/make_transactions.py <path to online_retail_II.xlsx or online_retail_ii.csv>

Writes data-team/data/transactions.csv with the columns of data-team/schemas/transactions.json. Lines without a
customer are left out (they cannot be anyone's features); cancellations (invoices starting with C) are kept, as the
source system holds them, and the feature SQL leaves them out.

Chen, D. (2012). Online Retail II [Dataset]. UCI Machine Learning Repository. https://doi.org/10.24432/C5CG6D (CC BY 4.0)
"""

import sys
from pathlib import Path

import pandas as pd

OUT = Path(__file__).resolve().parents[1] / "data-team" / "data"
SRC = Path(sys.argv[1])
if SRC.suffix == ".xlsx":
    df = pd.concat(pd.read_excel(SRC, sheet_name=None, dtype={"Invoice": str, "StockCode": str}).values(),
                   ignore_index=True)
else:
    df = pd.read_csv(SRC, parse_dates=["InvoiceDate"], dtype={"Invoice": str, "StockCode": str})
df = df[df["Customer ID"].notna()]
out = pd.DataFrame({
    "invoice": df["Invoice"],
    "stock_code": df["StockCode"],
    "quantity": df["Quantity"],
    "invoice_date": df["InvoiceDate"].dt.strftime("%Y-%m-%d %H:%M:%S"),
    "price": df["Price"],
    "customer_id": df["Customer ID"].astype(int).astype(str),
    "country": df["Country"],
})
OUT.mkdir(parents=True, exist_ok=True)
out.to_csv(OUT / "transactions.csv", index=False)
print(f"transactions.csv: {len(out):,} lines, {out['customer_id'].nunique():,} customers, "
      f"{out['invoice_date'].min()} to {out['invoice_date'].max()}")
