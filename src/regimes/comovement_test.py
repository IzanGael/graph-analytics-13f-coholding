"""Co-movement test: which grouping of stocks, known at quarter t, best explains returns from t to t+1? (no look-ahead)

Groupings at t: bet tribes (conviction graph, best of 20 Louvain runs), ownership groups (ownership graph, same),
Fama-French 12 and 48 sectors, size quintiles. Stocks: the 1,000 of quarter t that are in the largest component of
both graphs, have a sector and a valid return (returns winsorised at 1% / 99% per period).
Measures per period:
- R2 = share of the cross-section of returns explained by group means (between-group variance / total)
- excess R2 = R2 minus the mean R2 of 200 random groupings with the same group sizes (more groups explain more by chance)
- incremental R2 of tribes (or ownership groups) on top of FF12 + size quintiles (OLS with group dummies), minus the
  same for random groupings
Down periods: median return of the stocks below -3%.
Usage: python comovement_test.py <repo folder> <folder with returns_13f.parquet>
"""
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import pandas as pd

REPO, D = Path(sys.argv[1]), Path(sys.argv[2])
I = REPO / "data" / "interim"
Q = [f"{y}Q{q}" for y in range(2021, 2027) for q in range(1, 5) if "2021Q4" <= f"{y}Q{q}" <= "2026Q2"]
rng = np.random.default_rng(42)
R = pd.read_parquet(D / "returns_13f.parquet")
R = R[~R.dropped]


def best_groups(path):
    e = pd.read_parquet(path)
    G = nx.Graph(); G.add_weighted_edges_from(e[["source", "target", "z"]].itertuples(index=False))
    G = G.subgraph(max(nx.connected_components(G), key=len)).copy()
    best = max((nx.community.louvain_communities(G, weight="weight", seed=42 + s) for s in range(20)),
               key=lambda c: nx.community.modularity(G, c, weight="weight"))
    return {v: i for i, c in enumerate(best) for v in c}


def dummies(labels):
    return pd.get_dummies(pd.Series(labels).astype(str), drop_first=True).to_numpy(float)


def r2_ols(y, X):
    X = np.column_stack([np.ones(len(y)), X]) if X.size else np.ones((len(y), 1))
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    return 1 - ((y - X @ beta) ** 2).sum() / ((y - y.mean()) ** 2).sum()


def eta2(y, labels):
    df = pd.DataFrame({"y": y, "g": labels})
    m = df.groupby("g").y.transform("mean")
    return ((m - y.mean()) ** 2).sum() / ((y - y.mean()) ** 2).sum()


rows = []
for a, b in zip(Q, Q[1:]):
    nodes = pd.read_parquet(I / "graphs" / f"nodes_{a}.parquet")
    tribes = best_groups(I / "graphs_conviction" / f"edges_t2.0_{a}.parquet")
    own = best_groups(I / "graphs" / f"edges_k15_{a}.parquet")
    r = R[R.from_q == a].drop_duplicates("ISSUER").set_index("ISSUER").ret
    s = [v for v in nodes.index if v in tribes and v in own and v in r.index and pd.notna(nodes.at[v, "ff12"])]
    y = r.loc[s].clip(*r.loc[s].quantile([0.01, 0.99])).to_numpy()
    size = pd.qcut(nodes.loc[s, "value"].rank(method="first"), 5, labels=False).to_numpy()
    G = {"tribes": np.array([tribes[v] for v in s]), "ownership": np.array([own[v] for v in s]),
         "ff12": nodes.loc[s, "ff12"].to_numpy(), "ff48": nodes.loc[s, "ff48"].to_numpy(), "size": size}
    row = {"period": f"{a}->{b}", "stocks": len(s), "median_return": float(np.median(y))}
    for k, lab in G.items():
        obs = eta2(y, lab)
        null = [eta2(y, rng.permutation(lab)) for _ in range(200)]
        row[f"groups_{k}"] = len(set(lab)); row[f"r2_{k}"] = obs
        row[f"excess_{k}"] = obs - np.mean(null); row[f"p_{k}"] = np.mean(np.array(null) >= obs)
    base = np.column_stack([dummies(G["ff12"]), dummies(G["size"])])
    r2_base = r2_ols(y, base)
    row["r2_ff12_size"] = r2_base
    for k in ("tribes", "ownership"):
        inc = r2_ols(y, np.column_stack([base, dummies(G[k])])) - r2_base
        null = [r2_ols(y, np.column_stack([base, dummies(rng.permutation(G[k]))])) - r2_base for _ in range(100)]
        row[f"incr_{k}"] = inc - np.mean(null); row[f"p_incr_{k}"] = np.mean(np.array(null) >= inc)
    rows.append(row)
    print({k: (round(v, 3) if isinstance(v, float) else v) for k, v in row.items()}, flush=True)

T = pd.DataFrame(rows)
T.to_csv(D / "comovement_by_period.csv", index=False)
down = T.median_return < -0.03
pd.set_option("display.width", 250)
summary = []
for k in ("tribes", "ownership", "ff12", "ff48", "size"):
    summary.append({"grouping": k, "groups_avg": T[f"groups_{k}"].mean(), "r2_avg": T[f"r2_{k}"].mean(),
                    "excess_r2_avg": T[f"excess_{k}"].mean(), "excess_r2_down": T.loc[down, f"excess_{k}"].mean(),
                    "excess_r2_up": T.loc[~down, f"excess_{k}"].mean(), "periods_p_below_0.05": int((T[f"p_{k}"] < 0.05).sum())})
S = pd.DataFrame(summary).round(3)
S.to_csv(D / "comovement_summary.csv", index=False)
print("\nperiods:", len(T), " down periods:", T.loc[down, "period"].tolist())
print(S.to_string(index=False))
for k in ("ownership", "ff12", "ff48", "size"):
    w = (T.excess_tribes > T[f"excess_{k}"]).sum()
    print(f"tribes beat {k} in {w}/{len(T)} periods (excess R2)")
print("\nincremental R2 over FF12 + size (minus random):")
for k in ("tribes", "ownership"):
    print(f"  {k}: mean {T[f'incr_{k}'].mean():.3f}, down {T.loc[down, f'incr_{k}'].mean():.3f}, "
          f"periods p<0.05: {(T[f'p_incr_{k}'] < 0.05).sum()}/{len(T)}")

fig, ax = plt.subplots(figsize=(10, 4.6))
xs = np.arange(len(T))
colors = {"tribes": "#d9480f", "ownership": "#4a6fa5", "ff12": "#868e96", "size": "#c2c7cc"}
for i, (k, c) in enumerate(colors.items()):
    ax.bar(xs + (i - 1.5) * 0.2, T[f"excess_{k}"], 0.2, color=c, label={"tribes": "Bet tribes", "ownership": "Ownership groups",
                                                                          "ff12": "Sectors (FF12)", "size": "Size quintiles"}[k])
for i in np.where(down)[0]:
    ax.axvspan(i - 0.5, i + 0.5, color="#fa5252", alpha=0.08, lw=0)
ax.axhline(0, color="#888", lw=0.8)
ax.set_xticks(xs, [p.split("->")[1] for p in T.period], rotation=90, fontsize=8)
ax.set_ylabel("Share of next-quarter returns explained\n(above random groupings)")
ax.set_title("Which grouping best predicts which stocks move together next quarter? Red bands = market down quarters", loc="left", fontsize=10)
ax.legend(frameon=False, ncol=4, fontsize=8)
for sp in ("top", "right"):
    ax.spines[sp].set_visible(False)
fig.tight_layout(); fig.savefig(D / "comovement_by_period.png", dpi=150)
print("saved")
