"""Read-only: which filers and rows explain implausible jumps in quarterly total value?

Compares each filer's total with its own median total across quarters. Changes no data.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))   # shared modules live in src/

import pandas as pd

from config import INTERIM, QUARTERS

totals, tops = {}, {}
for q in QUARTERS:
    h = pd.read_parquet(INTERIM / f"holdings_{q}.parquet", columns=["CIK", "NAMEOFISSUER", "CUSIP", "VALUE", "SHARES"])
    totals[q] = h.groupby("CIK")["VALUE"].sum()
    tops[q] = h.nlargest(4, "VALUE")[["CIK", "NAMEOFISSUER", "VALUE", "SHARES"]]
t = pd.DataFrame(totals)
med = t.median(axis=1)
names = pd.concat(pd.read_parquet(INTERIM / f"managers_{q}.parquet") for q in QUARTERS).drop_duplicates("CIK").set_index("CIK")["FILINGMANAGER_NAME"]
print("quarter | total $tn | median-of-filer total $tn | excess above 5x own median $tn | filers above")
for q in QUARTERS:
    excess = (t[q] - med)[t[q] > 5 * med]
    print(q, round(t[q].sum() / 1e12, 1), round(t[q].where(t[q] <= 5 * med).sum() / 1e12, 1), round(excess.sum() / 1e12, 1), len(excess))
    for cik, v in excess.nlargest(3).items():
        print(f"    {names.get(cik)}: ${t.loc[cik, q] / 1e12:.2f}tn vs usual ${med[cik] / 1e12:.3f}tn")
    print(tops[q].assign(VALUE=lambda d: (d["VALUE"] / 1e9).round(0), NAMEOFISSUER=lambda d: d["NAMEOFISSUER"].str[:24]).head(2).to_string(index=False, header=False))
