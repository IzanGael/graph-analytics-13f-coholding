"""Conviction graph: stocks linked when the same managers BET on both (relative overweight above a threshold).

Per quarter, same 1,000 stocks as the ownership graph (graphs/nodes_<q>.parquet):
- positions of filers with reliable values, managers with at least MIN_POS positions in the universe
- relative overweight = manager weight / neutral weight, neutral weight = market weight of the stock divided by the
  total market weight of the stocks this manager holds (market = all reliable 13F value in the universe)
- a bet = relative overweight > threshold (main 2.0; checks 1.5 and 3.0)
- stocks with fewer than MIN_BETTORS bettors are left out (their z-scores would be unreliable)
- same chance model (gutils.shared_holder_z_bicm), same backbone (top 15 partners, z > 3), 20 Louvain runs
Usage: python conviction_build.py <repo folder> <output folder>
Writes <repo>/data/interim/graphs_conviction/{nodes,edges}_t<thr>_<q>.parquet, <out>/conviction_runs_t<thr>.pkl,
<out>/conviction_graph_summary.csv
"""
import pickle, sys, time
from pathlib import Path

import networkx as nx
import numpy as np
import pandas as pd

REPO, OUT = Path(sys.argv[1]), Path(sys.argv[2])
sys.path.insert(0, str(REPO / "src"))
import gutils as gl
from config import INTERIM, ISSUER_ALIASES, QUARTERS, RECIPE

THRESHOLDS, MAIN_T, MIN_POS, MIN_BETTORS, RUNS, SEED = (2.0, 1.5, 3.0), 2.0, 10, 5, 20, 42
GDIR = INTERIM / "graphs_conviction"
GDIR.mkdir(exist_ok=True)


def bets_for_quarter(q):
    h = pd.read_parquet(INTERIM / f"holdings_{q}.parquet", columns=["CIK", "CUSIP", "VALUE", "VALUE_RELIABLE"])
    h["ISSUER"] = h["CUSIP"].str[:6].replace(ISSUER_ALIASES)
    pos = h.groupby(["CIK", "ISSUER"], as_index=False).agg(VALUE=("VALUE", "sum"), REL=("VALUE_RELIABLE", "all"))
    uni = pd.read_parquet(INTERIM / "graphs" / f"nodes_{q}.parquet")
    p = pos[pos["ISSUER"].isin(uni.index) & pos["REL"] & (pos["VALUE"] > 0)].copy()
    p = p[p.groupby("CIK")["ISSUER"].transform("size") >= MIN_POS]
    mkt = p.groupby("ISSUER")["VALUE"].sum()
    mkt = mkt / mkt.sum()
    p["w"] = p["VALUE"] / p.groupby("CIK")["VALUE"].transform("sum")
    p["W"] = p["ISSUER"].map(mkt)
    p["ow"] = p["w"] / (p["W"] / p.groupby("CIK")["W"].transform("sum"))
    return p, uni


rows, all_runs = [], {t: {} for t in THRESHOLDS}
for q in QUARTERS:
    t0 = time.time()
    p, uni = bets_for_quarter(q)
    for t in THRESHOLDS:
        b = p[p["ow"] > t][["CIK", "ISSUER"]]
        bettors = b.groupby("ISSUER")["CIK"].nunique()
        keep = bettors[bettors >= MIN_BETTORS].index
        u = uni.loc[uni.index.isin(keep)].copy()
        b = b[b["ISSUER"].isin(u.index)]
        fit = gl.shared_holder_z_bicm(b, u)
        names = list(u.index)
        G = gl.backbone(fit["z"], fit["C"], names, RECIPE["method"], RECIPE["top_k"], RECIPE["z_min"])
        u.assign(bettors=fit["k"]).to_parquet(GDIR / f"nodes_t{t}_{q}.parquet")
        pd.DataFrame([(a, c, d["weight"], d["shared"]) for a, c, d in G.edges(data=True)],
                     columns=["source", "target", "z", "shared"]).to_parquet(GDIR / f"edges_t{t}_{q}.parquet", index=False)
        H = G.subgraph([v for v in G if G.degree(v) > 0]).copy()
        runs = [{v: i for i, c in enumerate(nx.community.louvain_communities(H, weight="weight", seed=SEED + s)) for v in c}
                for s in range(RUNS)]
        all_runs[t][q] = runs
        best = max(range(RUNS), key=lambda s: nx.community.modularity(
            H, [{v for v, l in runs[s].items() if l == k} for k in set(runs[s].values())], weight="weight"))
        comms = [{v for v, l in runs[best].items() if l == k} for k in set(runs[best].values())]
        sizes = sorted(map(len, comms), reverse=True)
        rows.append({"quarter": q, "threshold": t, "managers_used": p["CIK"].nunique(), "bets": len(b),
                     "bets_pct_of_positions": round(100 * len(b) / len(p), 1), "stocks": len(u),
                     "stocks_dropped_few_bettors": len(uni) - len(u), "edges": G.number_of_edges(),
                     "linked_stocks": H.number_of_nodes(), "largest_component": len(max(nx.connected_components(H), key=len)),
                     "communities": len(sizes), "communities_10plus": sum(s >= 10 for s in sizes), "largest_community": sizes[0],
                     "modularity": round(nx.community.modularity(H, comms, weight="weight"), 3),
                     "solver_err": max(fit["err_stock_degree"], fit["err_manager_degree"])})
        print(rows[-1], flush=True)
    print(q, "done in", round(time.time() - t0), "s", flush=True)

pd.DataFrame(rows).to_csv(OUT / "conviction_graph_summary.csv", index=False)
for t in THRESHOLDS:
    with open(OUT / f"conviction_runs_t{t}.pkl", "wb") as f:
        pickle.dump(all_runs[t], f)
print("saved")
