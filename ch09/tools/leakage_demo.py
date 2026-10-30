"""Chapter 4: the same model trained twice, on point-in-time features and on a "latest values" view.

    pip install pandas scikit-learn
    python tools/leakage_demo.py

Reads usecases/lapse-risk/data/snapshots.csv (point in time: each row's features use only the year before its
cut-off) and data-team/data/transactions.csv (from tools/make_transactions.py). The leaky version gives every row
the customer's latest values, computed on the day the data ends, as a view that joins "current" features would.
Both train on cut-offs before March 2011 and are scored on the later ones; the leaky model is then scored again on
the features production would really have had at each cut-off.
"""

from pathlib import Path

import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score

ROOT = Path(__file__).resolve().parents[1]
FEATURES = ["recency_days", "orders_12m", "spend_12m_gbp", "distinct_products"]

pit = pd.read_csv(ROOT / "usecases" / "lapse-risk" / "data" / "snapshots.csv", dtype={"customer_id": str})

tx = pd.read_csv(ROOT / "data-team" / "data" / "transactions.csv", dtype={"customer_id": str, "invoice": str},
                 parse_dates=["invoice_date"])
buys = tx[~tx["invoice"].str.startswith("C") & (tx["quantity"] > 0)].copy()
buys["value"] = buys["quantity"] * buys["price"]
today = pd.Timestamp("2011-12-10")                  # the day after the last transaction
recent = buys[buys["invoice_date"] >= today - pd.Timedelta(days=365)].groupby("customer_id")
latest = pd.DataFrame({
    "recency_days": (today - buys.groupby("customer_id")["invoice_date"].max()).dt.days,
    "orders_12m": recent["invoice"].nunique(),
    "spend_12m_gbp": recent["value"].sum().round(2),
    "distinct_products": recent["stock_code"].nunique(),
}).fillna(0)
leaky = pit[["customer_id", "snapshot_date", "lapsed"]].join(latest, on="customer_id")


def auc(trained_on: pd.DataFrame, scored_on: pd.DataFrame) -> float:
    train = trained_on[trained_on["snapshot_date"] < "2011-03-01"]
    test = scored_on[scored_on["snapshot_date"] >= "2011-03-01"]
    model = HistGradientBoostingClassifier(random_state=0).fit(train[FEATURES], train["lapsed"])
    return roc_auc_score(test["lapsed"], model.predict_proba(test[FEATURES])[:, 1])


print(f"point in time, evaluated as trained:            AUC {auc(pit, pit):.3f}")
print(f"latest values, evaluated as trained:            AUC {auc(leaky, leaky):.3f}")
print(f"latest values, scored on what production knows: AUC {auc(leaky, pit):.3f}")
