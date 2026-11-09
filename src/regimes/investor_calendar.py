"""Investor calendar: let the data define regimes from the similarity of investor groups between quarters.

1. Similarity matrix S (19 x 19): mean ARI over all 20 x 20 pairs of Louvain runs between two quarters (less noisy
   than comparing one run per quarter). Diagonal = run-to-run ARI within the quarter (Louvain's own noise).
2. Contiguous segmentation by dynamic programming, for k = 1..8 blocks. Cost of a block = sum over its quarter pairs of
   (1 - S) divided by the block size (within-block spread, as in k-means). Best cuts minimise the total cost.
3. Smooth-drift baseline: keep the average similarity at each time gap, shuffle the residuals along each diagonal
   (same gap), and segment again. The cuts are real only if they explain more than in these drift-only matrices.
4. Break strength at each transition: mean similarity inside a 2-quarter window on each side minus mean similarity across.
Usage: python investor_calendar.py <repo folder> <output folder>
"""
import itertools, sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import pandas as pd
from sklearn.metrics import adjusted_rand_score as ari

REPO, OUT = Path(sys.argv[1]), Path(sys.argv[2])
G_DIR = REPO / "data" / "interim" / "graphs"
RUNS, SEED, KMAX, NULL_DRAWS, WIN = 20, 42, 8, 2000, 2
MACRO = [("2021Q4", "2022Q3", "Repricing"), ("2022Q4", "2023Q2", "Disinflation"), ("2023Q3", "2024Q4", "AI soft landing"),
         ("2025Q1", "2025Q2", "Tariff shock"), ("2025Q3", "2025Q4", "Boom + soft labor"), ("2026Q1", "2026Q2", "Energy shock")]
Q = [f"{y}Q{q}" for y in range(2021, 2027) for q in range(1, 5) if "2021Q4" <= f"{y}Q{q}" <= "2026Q2"]
n = len(Q)
macro_reg = np.array([next(i for i, (a, b, _) in enumerate(MACRO) if a <= q <= b) for q in Q])
macro_cuts = [i for i in range(1, n) if macro_reg[i] != macro_reg[i - 1]]   # cut before quarter index i

# 1. Louvain runs per quarter
runs = {}
for q in Q:
    e = pd.read_parquet(G_DIR / f"edges_k15_{q}.parquet")
    G = nx.Graph()
    G.add_weighted_edges_from(e[["source", "target", "z"]].itertuples(index=False))
    runs[q] = [{v: i for i, c in enumerate(nx.community.louvain_communities(G, weight="weight", seed=SEED + s)) for v in c}
               for s in range(RUNS)]
    print("louvain", q, flush=True)


def mean_ari(a, b):
    common = sorted(set(runs[a][0]) & set(runs[b][0]))
    if a == b:
        pairs = itertools.combinations(runs[a], 2)
    else:
        pairs = itertools.product(runs[a], runs[b])
    return float(np.mean([ari([x[v] for v in common], [y[v] for v in common]) for x, y in pairs]))


S = np.zeros((n, n))
for i in range(n):
    for j in range(i, n):
        S[i, j] = S[j, i] = mean_ari(Q[i], Q[j])
    print("ari row", Q[i], flush=True)
pd.DataFrame(S, index=Q, columns=Q).round(3).to_csv(OUT / "calendar_similarity_matrix.csv")


# 2. Optimal contiguous segmentation
def block_cost(M, a, b):          # quarters a..b-1
    m = b - a
    if m < 2:
        return 0.0
    sub = 1 - M[a:b, a:b]
    return float(sub[np.triu_indices(m, 1)].sum() / m)


def segment(M, kmax=KMAX):
    C = np.array([[block_cost(M, a, b) if b > a else np.inf for b in range(n + 1)] for a in range(n + 1)])
    best = np.full((kmax + 1, n + 1), np.inf); arg = np.zeros((kmax + 1, n + 1), int)
    best[0, 0] = 0
    for k in range(1, kmax + 1):
        for b in range(1, n + 1):
            vals = [best[k - 1, a] + C[a, b] for a in range(b)]
            arg[k, b] = int(np.argmin(vals)); best[k, b] = vals[arg[k, b]]
    out = {}
    for k in range(1, kmax + 1):
        cuts, b = [], n
        for kk in range(k, 0, -1):
            a = arg[kk, b]
            if a > 0:
                cuts.append(a)
            b = a
        out[k] = (best[k, n], sorted(cuts))
    return out


seg = segment(S)
total = seg[1][0]
rows = []
for k, (cost, cuts) in seg.items():
    blocks = [Q[a] + "-" + Q[b - 1] for a, b in zip([0] + cuts, cuts + [n])]
    rows.append({"k": k, "cost": round(cost, 3), "explained_pct": round(100 * (1 - cost / total), 1),
                 "cuts_before": ", ".join(Q[c] for c in cuts), "blocks": " | ".join(blocks),
                 "cuts_matching_macro": sum(c in macro_cuts for c in cuts)})
segtab = pd.DataFrame(rows)

# 3. Smooth-drift baseline
rng = np.random.default_rng(SEED)
lag_mean = {d: np.mean([S[i, i + d] for i in range(n - d)]) for d in range(1, n)}
null_expl = {k: [] for k in range(2, KMAX + 1)}
for _ in range(NULL_DRAWS):
    N = np.eye(n) * np.diag(S)
    for d in range(1, n):
        res = np.array([S[i, i + d] - lag_mean[d] for i in range(n - d)])
        rng.shuffle(res)
        for i in range(n - d):
            N[i, i + d] = N[i + d, i] = lag_mean[d] + res[i]
    sn = segment(N)
    for k in null_expl:
        null_expl[k].append(100 * (1 - sn[k][0] / sn[1][0]))
segtab["null_explained_mean"] = [np.nan] + [round(np.mean(null_expl[k]), 1) for k in range(2, KMAX + 1)]
segtab["p_vs_drift"] = [np.nan] + [round(float(np.mean(np.array(null_expl[k]) >= segtab.loc[k - 1, "explained_pct"])), 3)
                                    for k in range(2, KMAX + 1)]
segtab.to_csv(OUT / "calendar_segmentations.csv", index=False)
pd.set_option("display.width", 250); pd.set_option("display.max_colwidth", 120)
print(segtab.to_string(index=False))

# 4. Break strength per transition (cut before quarter c)
brk = []
for c in range(1, n):
    L = list(range(max(0, c - WIN), c)); R = list(range(c, min(n, c + WIN)))
    within = [S[i, j] for grp in (L, R) for i, j in itertools.combinations(grp, 2)]
    across = [S[i, j] for i in L for j in R]
    brk.append({"transition": f"{Q[c-1]}->{Q[c]}", "to": Q[c], "break_strength": round(np.mean(within) - np.mean(across), 4),
                "adjacent_similarity": round(S[c - 1, c], 3), "macro_boundary": c in macro_cuts})
brk = pd.DataFrame(brk)
brk.to_csv(OUT / "calendar_break_strength.csv", index=False)
print(brk.to_string(index=False))
print("\nmacro cuts before:", [Q[c] for c in macro_cuts])
print("diagonal (run-to-run noise):", np.round(np.diag(S), 3).tolist())

# Figures
fig, ax = plt.subplots(figsize=(10, 4.2))
colors = ["#d9480f" if m else "#4a6fa5" for m in brk["macro_boundary"]]
ax.bar(range(len(brk)), brk["break_strength"], color=colors, width=0.7)
ax.axhline(0, color="#888", lw=0.8)
ax.set_xticks(range(len(brk)), brk["to"], rotation=90, fontsize=8)
ax.set_ylabel("Break strength (higher = sharper change)")
ax.set_title("Where do investors reorganise? Break strength at each quarter (bar = change into that quarter)\n"
             "Orange = a macro regime boundary, blue = no macro boundary", loc="left", fontsize=10)
for s in ("top", "right"):
    ax.spines[s].set_visible(False)
fig.tight_layout(); fig.savefig(OUT / "calendar_break_strength.png", dpi=160)
print("saved figures")
