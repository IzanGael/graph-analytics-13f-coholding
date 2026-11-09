"""Test A: do stock-stock links change more at the 5 macro regime boundaries than at other quarter transitions?
Uses the link overlap (Jaccard) between consecutive quarters from results/graph_summary.csv; exact permutation test.
Usage: python regime_test.py <graph_summary.csv> <out folder>"""
import itertools, sys
from pathlib import Path
import numpy as np, pandas as pd
s = pd.read_csv(sys.argv[1])
OUT = Path(sys.argv[2])
reg = {}
for r,(a,b) in enumerate([("2021Q4","2022Q3"),("2022Q4","2023Q2"),("2023Q3","2024Q4"),("2025Q1","2025Q2"),("2025Q3","2025Q4"),("2026Q1","2026Q2")],1):
    for q in s.quarter:
        if a<=q<=b: reg[q]=r
s["regime"]=s.quarter.map(reg)
s["prev_regime"]=s.regime.shift()
t=s.dropna(subset=["edge_jaccard_common_stocks"]).copy()
t["boundary"]=t.regime!=t.prev_regime
print(t[["quarter","prev_regime","regime","boundary","stock_overlap","edge_jaccard_common_stocks"]].to_string(index=False))
for col in ["edge_jaccard_common_stocks","stock_overlap"]:
    x=t[col].values; b=t.boundary.values
    obs=x[~b].mean()-x[b].mean()
    combos=list(itertools.combinations(range(len(x)),b.sum()))
    null=[]
    for c in combos:
        m=np.zeros(len(x),bool); m[list(c)]=True
        null.append(x[~m].mean()-x[m].mean())
    null=np.array(null)
    print(f"\n{col}: inside={x[~b].mean():.3f} boundary={x[b].mean():.3f} diff={obs:.3f} exact p (one-sided)={(null>=obs).mean():.3f} over {len(combos)} placements")
s[["quarter","regime"]].to_csv(OUT / "quarter_regime.csv",index=False)
