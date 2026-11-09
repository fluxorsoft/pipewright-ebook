"""Chapter 11: candidate lapse features, measured before anything is built.

    pip install pandas openpyxl scikit-learn
    python tools/candidate_features.py <path to online_retail_II.xlsx or online_retail_ii.csv>

Computes seven candidates as of each monthly cut-off (only the year before it), adds each in turn to the four
features the lapse model has, and prints the test AUC on the book's time split; then all of them, and all but each.
Compare every change with the noise between random seeds (about 0.002 here) before building anything.
"""
import sys

import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score
SRC = sys.argv[1]
if SRC.endswith(".xlsx"):
    df = pd.concat(pd.read_excel(SRC, sheet_name=None, dtype={"Invoice": str, "StockCode": str}).values(),
                   ignore_index=True)
else:
    df = pd.read_csv(SRC, parse_dates=["InvoiceDate"], dtype={"Invoice": str, "StockCode": str})
df = df[df["Customer ID"].notna()].copy()
df["cid"] = df["Customer ID"].astype(int).astype(str)
df["value"] = df["Quantity"] * df["Price"]
df["cancel"] = df["Invoice"].str.startswith("C")
df["xmas"] = df["Description"].fillna("").str.contains("CHRISTMAS")
buys = df[~df.cancel & (df.Quantity > 0)]
cuts = pd.date_range("2010-06-01", "2011-09-01", freq="MS")
rows = []
for c in cuts:
    y = buys[(buys.InvoiceDate < c) & (buys.InvoiceDate >= c - pd.Timedelta(days=365))]
    y3 = y[y.InvoiceDate >= c - pd.Timedelta(days=91)]
    allp = buys[buys.InvoiceDate < c]
    canc = df[df.cancel & (df.InvoiceDate < c) & (df.InvoiceDate >= c - pd.Timedelta(days=365))]
    g = y.groupby("cid")
    f = pd.DataFrame({
        "recency_days": (c - g.InvoiceDate.max()).dt.days,
        "orders_12m": g.Invoice.nunique(),
        "spend_12m_gbp": g.value.sum(),
        "distinct_products": g.StockCode.nunique(),
    })
    f["orders_3m"] = y3.groupby("cid").Invoice.nunique().reindex(f.index).fillna(0)
    f["spend_3m_share"] = (y3.groupby("cid").value.sum().reindex(f.index).fillna(0) / f.spend_12m_gbp.clip(lower=1))
    f["tenure_days"] = (c - allp.groupby("cid").InvoiceDate.min()).dt.days.reindex(f.index)
    f["active_months_12m"] = y.groupby("cid").InvoiceDate.apply(lambda s: s.dt.to_period("M").nunique())
    od = y.groupby(["cid", "Invoice"]).InvoiceDate.min().reset_index().sort_values(["cid", "InvoiceDate"])
    od["gap"] = od.groupby("cid").InvoiceDate.diff().dt.days
    f["avg_days_between_orders"] = od.groupby("cid").gap.mean().reindex(f.index)
    f["return_rate"] = (canc.groupby("cid").Invoice.nunique().reindex(f.index).fillna(0) / f.orders_12m)
    f["xmas_share"] = y[y.xmas].groupby("cid").value.sum().reindex(f.index).fillna(0) / f.spend_12m_gbp.clip(lower=1)
    later = buys[(buys.InvoiceDate >= c) & (buys.InvoiceDate < c + pd.Timedelta(days=90))].cid.unique()
    f["returned"] = f.index.isin(later).astype(int)
    f["snapshot_date"] = c
    rows.append(f.reset_index())
d = pd.concat(rows, ignore_index=True)
cut = sorted(d.snapshot_date.unique())[int(len(cuts) * 0.8)]
tr, te = d[d.snapshot_date < cut], d[d.snapshot_date >= cut]
base = ["recency_days", "orders_12m", "spend_12m_gbp", "distinct_products"]
cands = ["orders_3m", "spend_3m_share", "tenure_days", "active_months_12m", "avg_days_between_orders", "return_rate", "xmas_share"]
def auc(feats):
    m = HistGradientBoostingClassifier(random_state=0).fit(tr[feats], tr.returned)
    return roc_auc_score(te.returned, m.predict_proba(te[feats])[:, 1])
b = auc(base); print(f"rows {len(d)}  base AUC {b:.4f}")
for c_ in cands: print(f"  + {c_:24s} {auc(base+[c_]):.4f}  ({auc(base+[c_])-b:+.4f})")
allf = base + cands; a = auc(allf); print(f"all eleven       {a:.4f} ({a-b:+.4f})")
for c_ in cands: print(f"  all minus {c_:24s} {auc([x for x in allf if x!=c_]):.4f}")
