"""Read-only: who and what is behind the rows priced 2-300x their security's median in 2021 Q4?"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))   # shared modules live in src/

import numpy as np
import pandas as pd

from config import INTERIM

h = pd.read_parquet(INTERIM / "holdings_2021Q4.parquet", columns=["CIK", "NAMEOFISSUER", "CUSIP", "VALUE", "SHARES", "VALUE_RELIABLE"])
h["P"] = h["VALUE"] / h["SHARES"]
h["ratio"] = h["P"] / h["CUSIP"].map(h.groupby("CUSIP")["P"].median())
band = h[h["VALUE_RELIABLE"] & h["ratio"].between(2, 300)]
names = pd.concat(pd.read_parquet(INTERIM / f"managers_{q}.parquet") for q in ("2021Q4", "2022Q1")).drop_duplicates("CIK").set_index("CIK")["FILINGMANAGER_NAME"]
print("rows", len(band), "filers", band["CIK"].nunique(), "securities", band["CUSIP"].nunique(), "$tn", round(band["VALUE"].sum() / 1e12, 2))
by = band.groupby("CIK")["VALUE"].agg(["size", "sum"]).sort_values("sum", ascending=False)
by["pct"] = (by["sum"] / by["sum"].sum() * 100).round(1)
by["manager"] = names.reindex(by.index).str[:34]
print(by.head(8).assign(sum=lambda d: (d["sum"] / 1e12).round(2)).to_string())
print("top 5 filers share of band value:", round(by["pct"].head(5).sum(), 1))
print("ratio quantiles:", band["ratio"].quantile([.1, .25, .5, .75, .9]).round(1).to_dict())
print("share of band rows with ratio near 1000/N for round N (e.g. 4,5,10,100):", {n: int(band["ratio"].between(n * .9, n * 1.1).sum()) for n in (4, 5, 10, 100)})
top = by.index[0]
f = h[h["CIK"] == top]
print("top filer all rows:", len(f), "rows in band:", int((f.index.isin(band.index)).sum()), "median ratio:", round(f["ratio"].median(), 1))
print(f.nlargest(5, "VALUE")[["NAMEOFISSUER", "VALUE", "SHARES", "P", "ratio"]].round(1).to_string(index=False))
