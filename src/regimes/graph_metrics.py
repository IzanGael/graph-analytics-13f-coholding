"""Required graph measures for both graphs (ownership: edges_k15; conviction: edges_t2.0), all 19 quarters, plus
centralities for one detailed quarter.

Conventions: undirected simple graphs. Components on all 1,000 stocks (isolated stocks count as components).
Diameter and radius on the largest connected component, in hops (unweighted): the z weight is a similarity, not a distance.
Centralities (detailed quarter, largest component): degree, strength (sum of z), betweenness (exact, unweighted),
closeness (unweighted), eigenvector (weighted by z), PageRank (weighted by z, alpha 0.85), core number (k-core).
Bridge score: participation coefficient P = 1 - sum_c (k_ic / k_i)^2 over Louvain groups (0 = all links inside its own group).
Usage: python graph_metrics.py <repo folder> <out folder> <detail quarter>
"""
import sys
from pathlib import Path

import networkx as nx
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

REPO, OUT, DQ = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
I = REPO / "data" / "interim"
Q = [f"{y}Q{q}" for y in range(2021, 2027) for q in range(1, 5) if "2021Q4" <= f"{y}Q{q}" <= "2026Q2"]
GRAPHS = {"ownership": (I / "graphs", "edges_k15_{q}.parquet", "nodes_{q}.parquet"),
          "conviction": (I / "graphs_conviction", "edges_t2.0_{q}.parquet", "nodes_t2.0_{q}.parquet")}


def load(kind, q):
    d, ef, nf = GRAPHS[kind]
    nodes = pd.read_parquet(d / nf.format(q=q))
    e = pd.read_parquet(d / ef.format(q=q))
    G = nx.Graph(); G.add_nodes_from(nodes.index)
    G.add_weighted_edges_from(e[["source", "target", "z"]].itertuples(index=False))
    return G, nodes


rows = []
for kind in GRAPHS:
    for q in Q:
        G, _ = load(kind, q)
        comps = sorted(nx.connected_components(G), key=len, reverse=True)
        L = G.subgraph(comps[0])
        ecc = nx.eccentricity(L)
        rows.append({"graph": kind, "quarter": q, "nodes": G.number_of_nodes(), "edges": G.number_of_edges(),
                     "density": round(nx.density(G), 4), "mean_degree": round(2 * G.number_of_edges() / G.number_of_nodes(), 1),
                     "components": len(comps), "isolated": sum(len(c) == 1 for c in comps), "largest_component": len(comps[0]),
                     "second_component": len(comps[1]) if len(comps) > 1 else 0,
                     "diameter_lcc": max(ecc.values()), "radius_lcc": min(ecc.values()),
                     "avg_shortest_path_lcc": round(nx.average_shortest_path_length(L), 2),
                     "clustering": round(nx.average_clustering(G), 3)})
        print(rows[-1], flush=True)
m = pd.DataFrame(rows)
m.to_csv(OUT / "graph_metrics_all_quarters.csv", index=False)
pd.set_option("display.width", 250)
print(m.groupby("graph").agg(["min", "max"]).T.to_string())

# Centralities, detailed quarter
for kind in GRAPHS:
    G, nodes = load(kind, DQ)
    L = G.subgraph(max(nx.connected_components(G), key=len)).copy()
    best = max((nx.community.louvain_communities(L, weight="weight", seed=42 + s) for s in range(20)),
               key=lambda c: nx.community.modularity(L, c, weight="weight"))
    lab = {v: i for i, c in enumerate(sorted(best, key=len, reverse=True)) for v in c}
    c = pd.DataFrame(index=list(L))
    c["name"] = nodes.loc[c.index, "NAME"]; c["ticker"] = nodes.loc[c.index, "ticker"]
    c["ff12"] = nodes.loc[c.index, "ff12"]; c["value_bn"] = (nodes.loc[c.index, "value"] / 1e9).round(1)
    c["holders_or_bettors"] = nodes.loc[c.index, "holders" if kind == "ownership" else "bettors"]
    c["group"] = pd.Series(lab) + 1
    c["degree"] = pd.Series(dict(L.degree()))
    c["strength"] = pd.Series(dict(L.degree(weight="weight"))).round(1)
    c["betweenness"] = pd.Series(nx.betweenness_centrality(L))
    c["closeness"] = pd.Series(nx.closeness_centrality(L))
    c["eigenvector"] = pd.Series(nx.eigenvector_centrality_numpy(L, weight="weight"))
    c["pagerank"] = pd.Series(nx.pagerank(L, weight="weight"))
    c["core"] = pd.Series(nx.core_number(L))
    c["participation"] = [1 - sum((sum(1 for u in L[v] if lab[u] == g) / L.degree(v)) ** 2 for g in {lab[u] for u in L[v]}) for v in c.index]
    c.to_csv(OUT / f"centralities_{kind}_{DQ}.csv")
    print(f"\n===== {kind} {DQ}: largest component {L.number_of_nodes()} stocks, max core {c.core.max()} =====")
    cols = ["degree", "strength", "betweenness", "closeness", "eigenvector", "pagerank", "participation"]
    print("Spearman with value (size) and holders:")
    print(pd.DataFrame({col: [spearmanr(c[col], c.value_bn)[0], spearmanr(c[col], c.holders_or_bettors)[0]] for col in cols},
                       index=["vs size", "vs holders/bettors"]).round(2).to_string())
    print("Spearman between centralities:\n", c[cols].corr("spearman").round(2).to_string())
    for col in ["degree", "betweenness", "eigenvector", "pagerank", "participation"]:
        top = c.sort_values(col, ascending=False).head(10)
        print(f"top {col}: " + ", ".join(f"{(t if isinstance(t, str) else n[:12])}(g{g})" for t, n, g in zip(top.ticker, top.name, top.group)))
    print("innermost core:", c[c.core == c.core.max()].shape[0], "stocks; groups:", c[c.core == c.core.max()].group.value_counts().head(5).to_dict())
