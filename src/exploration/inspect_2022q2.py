"""Read-only: why is 2022 Q2 still too high? Tests rows against neighbouring quarters' prices."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))   # shared modules live in src/

import numpy as np
import pandas as pd

from config import INTERIM

QS = ["2022Q1", "2022Q2", "2022Q3"]
data = {q: pd.read_parquet(INTERIM / f"holdings_{q}.parquet", columns=["CIK", "NAMEOFISSUER", "CUSIP", "VALUE", "SHARES", "VALUE_RELIABLE"]) for q in QS}
med = {}
for q, h in data.items():
    h["P"] = h["VALUE"] / h["SHARES"]
    med[q] = h.groupby("CUSIP")["P"].median()
    print(q, "total reliable $tn", round(h.loc[h["VALUE_RELIABLE"], "VALUE"].sum() / 1e12, 1))

for q in ("2022Q2", "2022Q3"):
    prev = QS[QS.index(q) - 1]
    jump = (med[q] / med[prev]).dropna()
    print(q, "median price vs previous: pct within 0.5-2x", round(jump.between(.5, 2).mean() * 100, 1), "near 1000x", int(jump.between(300, 3000).sum()), "near 1/1000", int(jump.between(1 / 3000, 1 / 300).sum()), "of", len(jump))

h = data["2022Q2"]
ref = h["CUSIP"].map(med["2022Q1"])
h["ratio_q1"] = h["P"] / ref
h["ratio_own"] = h["P"] / h["CUSIP"].map(med["2022Q2"])
bins = [0, 1e-3 * 3, .5, 2, 300, 3000, np.inf]
labels = ["<1/300", "1/300-0.5", "0.5-2", "2-300", "300-3000", ">3000"]
rel = h[h["VALUE_RELIABLE"]]
for col in ("ratio_own", "ratio_q1"):
    g = rel.groupby(pd.cut(rel[col], bins, labels=labels), observed=False)["VALUE"].agg(["size", "sum"])
    g["sum"] = (g["sum"] / 1e12).round(2)
    print(col, "reliable rows: band, rows, $tn\n", g.to_string())
print("reliable rows with no Q1 price: $tn", round(rel.loc[rel["ratio_q1"].isna(), "VALUE"].sum() / 1e12, 2))
print(rel.nlargest(12, "VALUE")[["CIK", "NAMEOFISSUER", "CUSIP", "VALUE", "SHARES", "P", "ratio_own", "ratio_q1"]].round(2).to_string(index=False))
t = {q: d[d["VALUE_RELIABLE"]].groupby("CUSIP")["VALUE"].sum() for q, d in data.items()}
c = pd.DataFrame(t).dropna()
c["excess"] = c["2022Q2"] - c[["2022Q1", "2022Q3"]].max(axis=1)
names = h.drop_duplicates("CUSIP").set_index("CUSIP")["NAMEOFISSUER"]
print("Securities with most excess over neighbours ($bn):")
print(c.nlargest(12, "excess").div(1e9).round(0).join(names.str[:26]).to_string())
print("Total excess, top 20 / all positive ($tn):", round(c["excess"].nlargest(20).sum() / 1e12, 2), round(c["excess"].clip(lower=0).sum() / 1e12, 2))
