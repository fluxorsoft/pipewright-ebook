"""The lapse-risk training data: one row per active customer per monthly cut-off, from the real transactions.

    pip install pandas openpyxl
    python tools/make_snapshots.py <path to online_retail_II.xlsx or online_retail_ii.csv>

The dataset: https://archive.ics.uci.edu/static/public/502/online+retail+ii.zip (unzip it first).

Features use only the 365 days before each cut-off; the label `lapsed` is 1 when the customer buys nothing in the
90 days after it. Writes, under usecases/lapse-risk/data/:

  snapshots.csv           cut-offs 1 June 2010 to 1 September 2011, cancellations left out (the good file)
  snapshots_bad_monday.csv  the latest cut-off from an export that forgot to leave cancellations out (Chapter 3)

Chen, D. (2012). Online Retail II [Dataset]. UCI Machine Learning Repository. https://doi.org/10.24432/C5CG6D (CC BY 4.0)
"""

from pathlib import Path

import pandas as pd

import sys

OUT = Path(__file__).resolve().parents[1] / "usecases" / "lapse-risk" / "data"
SRC = Path(sys.argv[1])
if SRC.suffix == ".xlsx":
    df = pd.concat(pd.read_excel(SRC, sheet_name=None, dtype={"Invoice": str, "StockCode": str}).values(),
                   ignore_index=True)
else:
    df = pd.read_csv(SRC, parse_dates=["InvoiceDate"], dtype={"Invoice": str, "StockCode": str})
df = df[df["Customer ID"].notna()].copy()
df["customer_id"] = df["Customer ID"].astype(int).astype(str)
df["value"] = df["Quantity"] * df["Price"]
df["cancelled"] = df["Invoice"].str.startswith("C")
CUTOFFS = pd.date_range("2010-06-01", "2011-09-01", freq="MS")
LABEL_DAYS, HISTORY_DAYS = 90, 365


def snapshot(lines: pd.DataFrame, purchases: pd.DataFrame, cutoff: pd.Timestamp) -> pd.DataFrame:
    """Features from `lines` (the year before the cut-off); the label from real purchases after it."""
    past = lines[(lines["InvoiceDate"] < cutoff) & (lines["InvoiceDate"] >= cutoff - pd.Timedelta(days=HISTORY_DAYS))]
    g = past.groupby("customer_id")
    feats = pd.DataFrame({
        "recency_days": (cutoff - g["InvoiceDate"].max()).dt.days,
        "orders_12m": g["Invoice"].nunique(),
        "spend_12m_gbp": g["value"].sum().round(2),
        "distinct_products": g["StockCode"].nunique(),
        "country": g["Country"].agg(lambda s: s.mode().iat[0]),
    })
    later = purchases[(purchases["InvoiceDate"] >= cutoff)
                      & (purchases["InvoiceDate"] < cutoff + pd.Timedelta(days=LABEL_DAYS))]
    feats["lapsed"] = (~feats.index.isin(later["customer_id"].unique())).astype(int)
    feats["snapshot_date"] = cutoff.date()
    return feats.reset_index()[["customer_id", "snapshot_date", "recency_days", "orders_12m", "spend_12m_gbp",
                                "distinct_products", "country", "lapsed"]]


purchases = df[~df["cancelled"] & (df["Quantity"] > 0)]
good = pd.concat([snapshot(purchases, purchases, c) for c in CUTOFFS], ignore_index=True)
OUT.mkdir(parents=True, exist_ok=True)
good.to_csv(OUT / "snapshots.csv", index=False)
print(f"snapshots.csv: {len(good):,} rows, {good['customer_id'].nunique():,} customers, "
      f"{len(CUTOFFS)} cut-offs, lapsed rate {good['lapsed'].mean():.1%}")

# The bad Monday: the same latest cut-off, from an export that kept cancelled invoices (negative values).
bad = snapshot(df, purchases, CUTOFFS[-1])
bad.to_csv(OUT / "snapshots_bad_monday.csv", index=False)
neg = int((bad["spend_12m_gbp"] < 0).sum())
print(f"snapshots_bad_monday.csv: {len(bad):,} rows, {neg} with negative spend, "
      f"{int((bad['orders_12m'] != good[good['snapshot_date'] == CUTOFFS[-1].date()].set_index('customer_id').reindex(bad['customer_id'])['orders_12m'].values).sum())} "
      f"with a different order count")
