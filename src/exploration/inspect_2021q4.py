"""Read-only: is 2021 Q4 still inflated? Compares price bands against 2022 Q1 and each security's total value."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))   # shared modules live in src/

import numpy as np
import pandas as pd

from config import INTERIM

cols = ["CIK", "NAMEOFISSUER", "CUSIP", "VALUE", "SHARES", "VALUE_RELIABLE"]
a = pd.read_parquet(INTERIM / "holdings_2021Q4.parquet", columns=cols)
b = pd.read_parquet(INTERIM / "holdings_2022Q1.parquet", columns=cols)
for h in (a, b):
    h["P"] = h["VALUE"] / h["SHARES"]
med_b = b.groupby("CUSIP")["P"].median()
med_a = a.groupby("CUSIP")["P"].median()
print("reliable totals $tn: 21Q4", round(a.loc[a["VALUE_RELIABLE"], "VALUE"].sum() / 1e12, 1), " 22Q1", round(b.loc[b["VALUE_RELIABLE"], "VALUE"].sum() / 1e12, 1))

a["ratio_next"] = a["P"] / a["CUSIP"].map(med_b)
a["ratio_own"] = a["P"] / a["CUSIP"].map(med_a)
rel = a[a["VALUE_RELIABLE"]]
labels = ["<1/300", "1/300-0.5", "0.5-2", "2-300", "300-3000", ">3000"]
bins = [0, 1 / 300, .5, 2, 300, 3000, np.inf]
for col in ("ratio_own", "ratio_next"):
    g = rel.groupby(pd.cut(rel[col], bins, labels=labels), observed=False)["VALUE"].agg(["size", "sum"])
    g["sum"] = (g["sum"] / 1e12).round(2)
    print(col, "reliable rows: band, rows, $tn\n", g.to_string())

# Value by security against the next quarter, using only reliable filers
t = pd.DataFrame({"2021Q4": rel.groupby("CUSIP")["VALUE"].sum(), "2022Q1": b[b["VALUE_RELIABLE"]].groupby("CUSIP")["VALUE"].sum()}).dropna()
t["excess"] = t["2021Q4"] - t["2022Q1"]
names = a.drop_duplicates("CUSIP").set_index("CUSIP")["NAMEOFISSUER"].str[:26]
print("Largest drops from 21Q4 to 22Q1 ($bn):")
print(t.nlargest(12, "excess").div(1e9).round(0).join(names).to_string())
print("securities in both:", len(t), " total 21Q4 $tn", round(t["2021Q4"].sum() / 1e12, 1), " 22Q1", round(t["2022Q1"].sum() / 1e12, 1))
print("sum of positive excess, top 20 / all ($tn):", round(t["excess"].nlargest(20).sum() / 1e12, 2), round(t["excess"].clip(lower=0).sum() / 1e12, 2))
print("share of the drop explained by securities whose value fell >50%:", round(t.loc[t["2022Q1"] < 0.5 * t["2021Q4"], "excess"].sum() / t["excess"].sum(), 2))
print("2021Q4 price vs 2022Q1 for Apple/Microsoft/JPM medians:", {n: round(med_a.get(c, np.nan), 1) for n, c in {"Apple": "037833100", "Microsoft": "594918104", "JPM": "46625H100"}.items()}, {n: round(med_b.get(c, np.nan), 1) for n, c in {"Apple": "037833100", "Microsoft": "594918104", "JPM": "46625H100"}.items()})
filer_a = a.groupby("CIK")["VALUE"].sum()
filer_b = b.groupby("CIK")["VALUE"].sum()
both = pd.concat([filer_a, filer_b], axis=1, keys=["a", "b"]).dropna()
both["r"] = both["a"] / both["b"]
print("filers present in both quarters:", len(both), " median ratio 21Q4/22Q1:", round(both["r"].median(), 3), " ratio of totals:", round(both["a"].sum() / both["b"].sum(), 3))
print("filers where ratio >5:", int((both["r"] > 5).sum()), " $tn in them (21Q4):", round(both.loc[both["r"] > 5, "a"].sum() / 1e12, 1), " ratio 1.5-5:", int(both["r"].between(1.5, 5).sum()), " $tn:", round(both.loc[both["r"].between(1.5, 5), "a"].sum() / 1e12, 1))
