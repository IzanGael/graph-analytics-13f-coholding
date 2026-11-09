"""Probe for the conviction graph on one quarter: how allocations look and how many positions each overweight rule keeps.
Usage: python conviction_probe.py <repo folder> <quarter>"""
import sys
from pathlib import Path
import numpy as np, pandas as pd
REPO = Path(sys.argv[1]); q = sys.argv[2]
sys.path.insert(0, str(REPO / "src"))
import gutils as gl
from config import INTERIM

h = pd.read_parquet(INTERIM / f"holdings_{q}.parquet", columns=["CIK", "CUSIP", "VALUE", "VALUE_RELIABLE"])
h["ISSUER"] = h["CUSIP"].str[:6].replace(gl.ISSUER_ALIASES)
pos = h.groupby(["CIK", "ISSUER"], as_index=False).agg(VALUE=("VALUE", "sum"), REL=("VALUE_RELIABLE", "all"))
uni = pd.read_parquet(REPO / "data/interim/graphs" / f"nodes_{q}.parquet")
p = pos[pos.ISSUER.isin(uni.index)].copy()
print("positions in universe:", len(p), " managers:", p.CIK.nunique())
print("positions from filers with unreliable values: %.1f%%" % (100 * (~p.REL).mean()))
p = p[p.REL & (p.VALUE > 0)].copy()
mkt = p.groupby("ISSUER").VALUE.sum(); mkt = mkt / mkt.sum()                       # market weight (13F aggregate)
p["w"] = p.VALUE / p.groupby("CIK").VALUE.transform("sum")                         # manager's portfolio weight
p["W"] = p.ISSUER.map(mkt)
p["ow_abs"] = p.w / p.W                                                             # vs whole market
p["ow_rel"] = p.w / (p.W / p.groupby("CIK").W.transform("sum"))                    # vs market-proportional mix of its own holdings
n = p.groupby("CIK").size(); p["npos"] = p.CIK.map(n)
print("\nmanagers by positions in universe:", n.describe(percentiles=[.1, .25, .5, .75, .9]).round(0).to_dict())
for col in ["ow_abs", "ow_rel"]:
    print(f"\n{col}: median {p[col].median():.2f}")
    for t in (1.5, 2, 3):
        print(f"  share of positions with {col} > {t}: {100*(p[col] > t).mean():.1f}%")
    print("  share > 2 by manager size:", p.assign(b=pd.cut(p.npos, [0, 10, 50, 200, 500, 1000])).groupby("b", observed=True)[col].apply(lambda s: round(100 * (s > 2).mean(), 1)).to_dict())
top = uni.sort_values("value", ascending=False).head(8).index
print("\nshare of holders that overweight (ow_rel > 2) the biggest stocks:")
for s in top:
    sub = p[p.ISSUER == s]
    print(f"  {uni.loc[s,'NAME'][:28]:28s} holders {len(sub):5d}  >2: {100*(sub.ow_rel > 2).mean():5.1f}%")
# example: a mid-size manager
ex = n[(n > 15) & (n < 40)].index[0]
e = p[p.CIK == ex].assign(name=lambda d: d.ISSUER.map(uni.NAME)).sort_values("w", ascending=False)
print(f"\nexample manager {ex} ({len(e)} stocks):")
print(e[["name", "w", "W", "ow_abs", "ow_rel"]].head(8).round(4).to_string(index=False))
