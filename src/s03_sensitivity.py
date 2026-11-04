"""Step 3: compare graph recipes so that the final filter is chosen on evidence.

For each recipe on the main quarter: size, connectivity, modularity, seed stability, how strongly
degree still follows popularity, agreement with the baseline partition, and persistence versus the
previous quarter. Output: results/sensitivity.csv
"""
from itertools import combinations

import networkx as nx
import numpy as np
import pandas as pd
from sklearn.metrics import adjusted_rand_score, normalized_mutual_info_score

import graphlib as gl
from config import MAIN_QUARTER, QUARTERS, RESULTS

BASE = dict(n=1000, low=10, high=200, method="knn", top_k=15, z_min=3.0)
RECIPES = {
    "baseline knn15 z3 mgr10-200": {},
    "knn10": {"top_k": 10},
    "knn25": {"top_k": 25},
    "z5": {"z_min": 5.0},
    "global z8": {"method": "global", "z_min": 8.0},
    "global z12": {"method": "global", "z_min": 12.0},
    "mgr5-500": {"low": 5, "high": 500},
    "mgr10-100": {"low": 10, "high": 100},
    "mgr all": {"low": 1, "high": None},
    "n500": {"n": 500},
    "n1500": {"n": 1500},
}


def build(quarter, imap, cfg, cache):
    if quarter not in cache:
        cache[quarter] = gl.load_positions(quarter)
    pos = cache[quarter]
    uni = gl.universe(pos, imap, cfg["n"])
    p = gl.restrict_managers(pos, uni, cfg["low"], cfg["high"])
    C, z, k, m = gl.shared_holder_z(p, uni)
    G = gl.backbone(z, C, list(uni.index), cfg["method"], cfg["top_k"], cfg["z_min"])
    return G, uni, pd.Series(k, index=uni.index), m


def main():
    imap = gl.issuer_map()
    quarters = list(QUARTERS)
    previous = quarters[quarters.index(MAIN_QUARTER) - 1]
    cache = {}
    rows, base_part = [], None
    for name, change in RECIPES.items():
        cfg = {**BASE, **change}
        G, uni, holders, m = build(MAIN_QUARTER, imap, cfg, cache)
        P, _, _, _ = build(previous, imap, cfg, cache)
        comps = sorted(nx.connected_components(G), key=len, reverse=True)
        lcc = G.subgraph(comps[0]).copy()
        runs = [gl.louvain(lcc, s) for s in range(5)]
        parts = [gl.as_labels(c) for c in runs]
        nodes = list(lcc)
        vec = lambda part, ns=nodes: [part[n] for n in ns]
        seed_ari = np.mean([adjusted_rand_score(vec(a), vec(b)) for a, b in combinations(parts, 2)])
        Q = [nx.community.modularity(lcc, c, weight="weight") for c in runs]
        best = parts[int(np.argmax(Q))]
        deg = pd.Series(dict(lcc.degree))
        degree_vs_holders = deg.corr(holders.reindex(deg.index), method="spearman")
        lcc_p = gl.largest_component(P)
        part_p = gl.as_labels(gl.louvain(lcc_p, 0))
        common = [n for n in nodes if n in part_p]
        e1, e2 = set(map(frozenset, G.edges)), set(map(frozenset, P.edges))
        y = uni.loc[nodes]
        row = {"recipe": name, "managers": m, "nodes": len(G), "edges": G.number_of_edges(),
               "components": len(comps), "lcc": len(lcc), "density": round(nx.density(G), 4),
               "k": len(runs[int(np.argmax(Q))]), "modularity": round(max(Q), 3),
               "seed_ari": round(seed_ari, 3), "degree_vs_holders": round(degree_vs_holders, 3),
               "edge_jaccard_prev": round(len(e1 & e2) / len(e1 | e2), 3),
               "quarter_ari": round(adjusted_rand_score(vec(best, common), vec(part_p, common)), 3),
               "nmi_ff12": round(normalized_mutual_info_score(y["ff12"], vec(best)), 3),
               "nmi_sic2": round(normalized_mutual_info_score(y["sic2"], vec(best)), 3)}
        if base_part is None:
            base_part = best
        shared = [n for n in nodes if n in base_part]
        row["ari_vs_baseline"] = round(adjusted_rand_score(vec(best, shared), vec(base_part, shared)), 3)
        rows.append(row)
        print(row, flush=True)
    pd.DataFrame(rows).to_csv(RESULTS / "sensitivity.csv", index=False)


if __name__ == "__main__":
    main()
