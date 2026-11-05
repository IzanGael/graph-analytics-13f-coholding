"""Step 4: build the main backbone graph for every quarter.

Per quarter: top 1,000 operating companies by value; all managers except any holding every stock; size-aware
chance model (gutils.shared_holder_z_bicm); each stock keeps its top-k partners with z above RECIPE["z_min"].
The main graph uses RECIPE["top_k"]; the sensitivity graphs use SENSITIVITY_K.
Output: data/interim/graphs/{nodes,z,edges_k*}_<quarter>, results/graph_summary.csv
"""
import time

import networkx as nx
import numpy as np
import pandas as pd

import gutils as gl
from config import INTERIM, N_ISSUERS, QUARTERS, RECIPE, RESULTS, SENSITIVITY_K

OUT = INTERIM / "graphs"


def edge_table(G):
    return pd.DataFrame([(u, v, d["weight"], d["shared"]) for u, v, d in G.edges(data=True)], columns=["source", "target", "z", "shared"])


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    imap = gl.issuer_map()
    main_k = RECIPE["top_k"]
    rows = []
    for q in QUARTERS:
        t0 = time.time()
        pos = gl.load_positions(q)
        uni = gl.universe(pos, imap, N_ISSUERS)
        p = pos[pos["ISSUER"].isin(uni.index)][["CIK", "ISSUER"]]
        fit = gl.shared_holder_z_bicm(p, uni)
        z, C, k = fit["z"], fit["C"], fit["k"]
        names = list(uni.index)
        uni.assign(holders=k).to_parquet(OUT / f"nodes_{q}.parquet")
        np.save(OUT / f"z_{q}.npy", z.astype(np.float32))
        row = {"quarter": q, "stocks": len(uni), "managers": fit["X"].shape[1], "links_manager_stock": int(k.sum()),
               "solver_iterations": fit["iterations"], "solver_error_stocks": fit["err_stock_degree"], "solver_error_managers": fit["err_manager_degree"],
               "pairs_z_above_3_pct": round(float((z[np.triu_indices(len(uni), 1)] > RECIPE["z_min"]).mean() * 100), 1)}
        for kk in (main_k, *SENSITIVITY_K):
            G = gl.backbone(z, C, names, RECIPE["method"], kk, RECIPE["z_min"])
            edge_table(G).to_parquet(OUT / f"edges_k{kk}_{q}.parquet", index=False)
            comps = sorted(nx.connected_components(G), key=len, reverse=True)
            row[f"edges_k{kk}"] = G.number_of_edges()
            if kk == main_k:
                row.update({"mean_degree": round(2 * G.number_of_edges() / len(uni), 1), "isolated": sum(1 for c in comps if len(c) == 1),
                            "components": len(comps), "largest_component": len(comps[0]), "density": round(nx.density(G), 4)})
        row["seconds"] = round(time.time() - t0)
        rows.append(row)
        print(row, flush=True)
    summary = pd.DataFrame(rows)

    # How much the graph changes from one quarter to the next (used for the persistence tests)
    overlap = []
    for a, b in zip(QUARTERS, list(QUARTERS)[1:]):
        na, nb = (set(pd.read_parquet(OUT / f"nodes_{x}.parquet").index) for x in (a, b))
        ea, eb = (pd.read_parquet(OUT / f"edges_k{main_k}_{x}.parquet") for x in (a, b))
        sa, sb = (set(map(frozenset, zip(e["source"], e["target"]))) for e in (ea, eb))
        common = na & nb
        sa_c, sb_c = ({e for e in s if e <= common} for s in (sa, sb))
        overlap.append({"quarter": b, "stocks_in_both": len(common), "stock_overlap": round(len(common) / len(na | nb), 3),
                        "edge_jaccard_common_stocks": round(len(sa_c & sb_c) / max(len(sa_c | sb_c), 1), 3)})
    summary = summary.merge(pd.DataFrame(overlap), on="quarter", how="left")
    summary.to_csv(RESULTS / "graph_summary.csv", index=False)
    cols = ["quarter", "stocks", "managers", "edges_k15", "mean_degree", "isolated", "components", "largest_component", "stock_overlap", "edge_jaccard_common_stocks", "seconds"]
    print(summary[[c for c in cols if c in summary]].to_string(index=False))


if __name__ == "__main__":
    main()
