"""Read-only: which securities does the median fix touch in pass 1, and what do their medians look like across quarters?"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))   # shared modules live in src/

import numpy as np
import pandas as pd

from config import INTERIM, QUARTERS
from s01b_flag_inflated import MIN_HOLDERS_FOR_PRICE, UNIT_BAND

quarters = list(QUARTERS)
medians, names = {}, {}
for q in quarters:
    h = pd.read_parquet(INTERIM / f"holdings_{q}.parquet", columns=["CIK", "NAMEOFISSUER", "CUSIP", "VALUE", "SHARES"])
    price = (h["VALUE"] / h["SHARES"]).groupby(h["CUSIP"]).median()
    medians[q] = price[h.groupby("CUSIP")["CIK"].nunique() >= MIN_HOLDERS_FOR_PRICE]
    for c, n in h.drop_duplicates("CUSIP").set_index("CUSIP")["NAMEOFISSUER"].items():
        names.setdefault(c, n)

flagged = {}
for i in range(1, len(quarters) - 1):
    q = quarters[i]
    ratios = pd.concat([medians[q] / medians[quarters[i - 1]], medians[q] / medians[quarters[i + 1]]], axis=1).dropna(how="all")
    high = ratios.apply(lambda r: r.dropna().between(*UNIT_BAND).all(), axis=1)
    low = ratios.apply(lambda r: r.dropna().between(1 / UNIT_BAND[1], 1 / UNIT_BAND[0]).all(), axis=1)
    flagged[q] = (list(high[high].index), list(low[low].index))
    if high.sum() + low.sum():
        print(q, "high:", int(high.sum()), "low:", int(low.sum()))
        # A neighbour that is missing leaves .all() to run over one ratio only
        one_sided = ratios.loc[(high | low)].isna().any(axis=1).sum()
        print("   flagged on a single neighbour (other side missing):", int(one_sided))

for q in ("2023Q2", "2024Q2"):
    i = quarters.index(q)
    codes = flagged[q][0] + flagged[q][1]
    print(f"\n== {q}: {len(codes)} securities flagged")
    for c in codes[:8]:
        series = [medians[quarters[j]].get(c, np.nan) for j in range(max(0, i - 2), min(len(quarters), i + 3))]
        print(f"  {names.get(c, '?')[:28]:28s} {c} medians {quarters[max(0, i - 2)]}..{quarters[min(len(quarters) - 1, i + 2)]}:", [round(float(x), 2) if x == x else None for x in series])
