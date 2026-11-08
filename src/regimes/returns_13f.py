"""Quarterly returns per issuer from 13F filings (price proxy = median value/shares across filers, per CUSIP).

Issuer return t -> t+1 uses the CUSIP most held at t (by total shares), priced at t and t+1.
Split fix: if the price ratio r and the ratio of total 13F shares s of that CUSIP point to a split (r < 0.6 and s > 1.5,
or r > 1.67 and s < 0.67), the return is r * k where k is the standard split ratio (2, 3, 4, 5, ..., 20, ...) nearest to s
(or its inverse for reverse splits), applied only if s is within 25% of k and the adjusted ratio is in [0.33, 3]. Returns outside [-80%, +300%] are dropped.
Prices are quarter-end medians across filers using reliable values only. Dividends are not included (price return).
Usage: python returns_13f.py <repo folder> <out folder>
"""
import sys
from pathlib import Path
import numpy as np, pandas as pd

REPO, OUT = Path(sys.argv[1]), Path(sys.argv[2])
I = REPO / "data" / "interim"
sys.path.insert(0, str(REPO / "src"))
from config import ISSUER_ALIASES
Q = [f"{y}Q{q}" for y in range(2021, 2027) for q in range(1, 5) if "2021Q4" <= f"{y}Q{q}" <= "2026Q2"]

px, sh = {}, {}
for q in Q:
    h = pd.read_parquet(I / f"holdings_{q}.parquet", columns=["CUSIP", "VALUE", "SHARES", "VALUE_RELIABLE"])
    h = h[(h.SHARES > 0) & (h.VALUE > 0)]
    sh[q] = h.groupby("CUSIP").SHARES.sum()
    r = h[h.VALUE_RELIABLE]
    g = (r.VALUE / r.SHARES).groupby(r.CUSIP)
    px[q] = g.median()[g.size() >= 5]          # need at least 5 reliable filers for a price
    print("prices", q, len(px[q]), flush=True)

STD = np.array([2, 3, 4, 5, 6, 8, 10, 12, 15, 20, 25, 30, 40, 50, 100], float)
rows = []
for a, b in zip(Q, Q[1:]):
    s0 = sh[a].to_frame("S0"); s0["ISSUER"] = s0.index.str[:6].map(lambda x: ISSUER_ALIASES.get(x, x))
    prim = s0.sort_values("S0").groupby("ISSUER").tail(1)            # most-held share class at t
    d = prim.join(px[a].rename("P0"), how="inner").join(px[b].rename("P1"), how="inner").join(sh[b].rename("S1"), how="inner")
    d["r_raw"] = d.P1 / d.P0; d["s"] = d.S1 / d.S0
    d["k"] = 1.0
    fwd = (d.r_raw < 0.6) & (d.s > 1.5); rev = (d.r_raw > 1 / 0.6) & (d.s < 1 / 1.5)
    snap = lambda x: STD[np.argmin(np.abs(np.log(STD) - np.log(x)))]   # nearest standard split ratio (log scale)
    d.loc[fwd, "k"] = d.loc[fwd, "s"].map(snap); d.loc[rev, "k"] = 1 / (1 / d.loc[rev, "s"]).map(snap)
    ok = (np.abs(np.log(d.s / d.k)) < np.log(1.25)) & (d.r_raw * d.k).between(1 / 3, 3)
    d["split_fixed"] = (fwd | rev) & ok
    d["ratio"] = np.where(d.split_fixed, d.r_raw * d.k, d.r_raw)
    d["ret"] = d.ratio - 1
    d["dropped"] = ~d.ret.between(-0.8, 3.0)
    d = d.reset_index().rename(columns={"index": "CUSIP"})
    d["from_q"], d["to_q"] = a, b
    rows.append(d[["from_q", "to_q", "ISSUER", "CUSIP", "P0", "P1", "s", "k", "split_fixed", "ret", "dropped"]])
    print(a, "->", b, "issuers", len(d), "splits fixed", int(d.split_fixed.sum()), "dropped", int(d.dropped.sum()),
          "median ret %.3f" % d.ret[~d.dropped].median(), flush=True)
R = pd.concat(rows)
R.to_parquet(OUT / "returns_13f.parquet", index=False)
# sanity checks on well-known moves (split-adjusted price returns)
chk = {"67066G": "NVIDIA", "023135": "AMAZON", "88160R": "TESLA", "02079K": "ALPHABET", "037833": "APPLE"}
print(R[R.ISSUER.isin(chk)].assign(name=lambda x: x.ISSUER.map(chk)).pivot_table(index="to_q", columns="name", values="ret").round(3).to_string())
print(R[R.split_fixed].merge(pd.read_parquet(I / "issuer_map.parquet")[["ISSUER", "NAME"]], on="ISSUER", how="left")
      [["to_q", "NAME", "k", "ret"]].sort_values("to_q").to_string(index=False))
