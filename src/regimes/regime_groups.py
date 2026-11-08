"""Group-level regime test (exploratory, not part of the repo pipeline yet).

Per quarter: Louvain on the main graph (edges_k15, weight = z), 20 seeds, keep the best-modularity run.
Then compare community memberships between quarters with ARI on stocks linked in both quarters.
Test 1: consecutive transitions, regime boundary vs inside a regime (exact permutation test).
Test 2: all quarter pairs, same regime vs different regime at equal time distance (lag).
"""
import itertools, sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import pandas as pd
from sklearn.metrics import adjusted_rand_score as ari, normalized_mutual_info_score as nmi

REPO = Path(sys.argv[1])
OUT = Path(sys.argv[2])
G_DIR = REPO / "data" / "interim" / "graphs"
REGIMES = [("2021Q4", "2022Q3", "Repricing"), ("2022Q4", "2023Q2", "Disinflation"), ("2023Q3", "2024Q4", "AI soft landing"),
           ("2025Q1", "2025Q2", "Tariff shock"), ("2025Q3", "2025Q4", "Boom + soft labor"), ("2026Q1", "2026Q2", "Energy shock")]
QUARTERS = [f"{y}Q{q}" for y in range(2021, 2027) for q in range(1, 5) if "2021Q4" <= f"{y}Q{q}" <= "2026Q2"]
regime = {q: i + 1 for i, (a, b, _) in enumerate(REGIMES) for q in QUARTERS if a <= q <= b}

labels, rows = {}, []
for q in QUARTERS:
    nodes = pd.read_parquet(G_DIR / f"nodes_{q}.parquet")
    e = pd.read_parquet(G_DIR / f"edges_k15_{q}.parquet")
    G = nx.Graph()
    G.add_weighted_edges_from(e[["source", "target", "z"]].itertuples(index=False))
    runs = []
    for s in range(20):
        c = nx.community.louvain_communities(G, weight="weight", seed=42 + s)
        runs.append((nx.community.modularity(G, c, weight="weight"), c))
    best = max(runs, key=lambda r: r[0])
    lab = {n: i for i, c in enumerate(best[1]) for n in c}
    run_labels = [[{n: i for i, c in enumerate(r[1]) for n in c}[n] for n in G] for r in runs]
    stab = np.mean([ari(a, b) for a, b in itertools.combinations(run_labels, 2)])
    sizes = sorted((len(c) for c in best[1]), reverse=True)
    ff = nodes.loc[list(G), "ff12"].fillna("NA")
    rows.append({"quarter": q, "regime": regime[q], "linked_stocks": G.number_of_nodes(), "communities": len(sizes),
                 "communities_10plus": sum(s >= 10 for s in sizes), "largest": sizes[0], "modularity": round(best[0], 3),
                 "seed_stability_ari": round(stab, 3), "nmi_vs_ff12": round(nmi(ff, [lab[n] for n in G]), 3)})
    labels[q] = lab
    print(rows[-1], flush=True)
per_q = pd.DataFrame(rows)
per_q.to_csv(OUT / "regime_communities_per_quarter.csv", index=False)


def pair_ari(a, b):
    common = sorted(set(labels[a]) & set(labels[b]))
    return ari([labels[a][n] for n in common], [labels[b][n] for n in common])


n = len(QUARTERS)
M = np.ones((n, n))
for i, j in itertools.combinations(range(n), 2):
    M[i, j] = M[j, i] = pair_ari(QUARTERS[i], QUARTERS[j])
pd.DataFrame(M, index=QUARTERS, columns=QUARTERS).round(3).to_csv(OUT / "regime_ari_matrix.csv")

# Test 1: consecutive transitions
t = pd.DataFrame({"to": QUARTERS[1:], "ari": [M[i, i + 1] for i in range(n - 1)],
                  "boundary": [regime[QUARTERS[i]] != regime[QUARTERS[i + 1]] for i in range(n - 1)]})
x, b = t["ari"].values, t["boundary"].values
obs = x[~b].mean() - x[b].mean()
null = []
for c in itertools.combinations(range(len(x)), int(b.sum())):
    m = np.zeros(len(x), bool); m[list(c)] = True
    null.append(x[~m].mean() - x[m].mean())
p1 = float((np.array(null) >= obs - 1e-12).mean())
print("\nTEST 1 consecutive quarters")
print(t.to_string(index=False))
print(f"inside={x[~b].mean():.3f} boundary={x[b].mean():.3f} gap={obs:.3f} p={p1:.3f}")

# Test 2: same vs different regime at equal lag; null = shift the five boundaries to random positions
def lag_gap(reg):
    gaps = []
    for lag in range(1, 6):
        same = [M[i, i + lag] for i in range(n - lag) if reg[i] == reg[i + lag]]
        diff = [M[i, i + lag] for i in range(n - lag) if reg[i] != reg[i + lag]]
        if same and diff:
            gaps.append(np.mean(same) - np.mean(diff))
    return np.mean(gaps)

reg_vec = [regime[q] for q in QUARTERS]
obs2 = lag_gap(reg_vec)
null2 = []
for cuts in itertools.combinations(range(1, n), 5):
    r = np.cumsum([1 if i in cuts else 0 for i in range(n)])
    null2.append(lag_gap(r))
p2 = float((np.array(null2) >= obs2 - 1e-12).mean())
print(f"\nTEST 2 same-regime minus different-regime ARI at equal lag (1-5): {obs2:.3f}, p={p2:.3f} over {len(null2)} boundary placements")

# Heatmap
fig, ax = plt.subplots(figsize=(8.5, 7.2))
im = ax.imshow(M, cmap="Blues", vmin=0, vmax=1)
ax.set_xticks(range(n), QUARTERS, rotation=90, fontsize=8)
ax.set_yticks(range(n), QUARTERS, fontsize=8)
starts = [i for i in range(n) if i == 0 or reg_vec[i] != reg_vec[i - 1]] + [n]
for k in range(len(starts) - 1):
    a, e_ = starts[k] - 0.5, starts[k + 1] - 0.5
    ax.add_patch(plt.Rectangle((a, a), e_ - a, e_ - a, fill=False, ec="#d9480f", lw=2))
    ax.text(e_ + 0.2, (a + e_) / 2, REGIMES[k][2], fontsize=8, va="center", color="#333")
for s in ax.spines.values():
    s.set_visible(False)
cb = fig.colorbar(im, ax=ax, fraction=0.04, pad=0.18)
cb.set_label("Community overlap (ARI): 1 = same groups, 0 = unrelated", fontsize=9)
ax.set_title("How similar are the investor groups between any two quarters?\nOrange squares = regimes", fontsize=11, loc="left")
fig.tight_layout()
fig.savefig(OUT / "regime_ari_heatmap.png", dpi=160)
print("saved", OUT / "regime_ari_heatmap.png")
