"""Step 4: required graph metrics, centralities and communities for the main quarter.

Outputs in results/: graph_stats.json, centrality.csv, communities.csv, community_summary.csv,
partition_comparison.csv, centrality_correlations.csv, community_managers.csv
"""
import json
from collections import Counter

import networkx as nx
import numpy as np
import pandas as pd
from sklearn.metrics import adjusted_rand_score, normalized_mutual_info_score

import graphlib as gl
from config import LOUVAIN_RUNS, MAIN_QUARTER, N_ISSUERS, RECIPE, RESULTS, SEED

rng = np.random.default_rng(SEED)


def compare(labels_a, labels_b, n_null=200):
    nmi = normalized_mutual_info_score(labels_a, labels_b)
    ari = adjusted_rand_score(labels_a, labels_b)
    null = [normalized_mutual_info_score(rng.permutation(labels_a), labels_b) for _ in range(n_null)]
    return round(nmi, 3), round(ari, 3), round(float(np.mean(null)), 3)


def main():
    imap = gl.issuer_map()
    pos = gl.load_positions(MAIN_QUARTER)
    uni = gl.universe(pos, imap, N_ISSUERS)
    p = gl.restrict_managers(pos, uni, RECIPE["low"], RECIPE["high"])
    C, z, k, m = gl.shared_holder_z(p, uni)
    names = list(uni.index)
    G = gl.backbone(z, C, names, RECIPE["method"], RECIPE["top_k"], RECIPE["z_min"])
    holders = pd.Series(k, index=names)

    comps = sorted(nx.connected_components(G), key=len, reverse=True)
    L = G.subgraph(comps[0]).copy()
    stats = {
        "quarter": MAIN_QUARTER, "recipe": RECIPE,
        "bipartite_managers_all": int(pos["CIK"].nunique()), "bipartite_issuers_all": int(pos["ISSUER"].nunique()),
        "bipartite_edges_all": len(pos), "managers_kept": m, "positions_kept": len(p),
        "raw_projection_edges": int((C > 0).sum() / 2), "raw_projection_density": float((C > 0).sum() / (len(k) * (len(k) - 1))),
        "nodes": G.number_of_nodes(), "edges": G.number_of_edges(), "density": nx.density(G),
        "connected": nx.is_connected(G), "components": [len(c) for c in comps],
        "lcc_nodes": L.number_of_nodes(), "diameter_hops": nx.diameter(L), "radius_hops": nx.radius(L),
        "center_size": len(nx.center(L)), "periphery_size": len(nx.periphery(L)),
        "average_shortest_path": nx.average_shortest_path_length(L),
        "average_clustering": nx.average_clustering(L), "main_core_k": max(nx.core_number(L).values()),
        "degree_min": min(d for _, d in L.degree), "degree_median": float(np.median([d for _, d in L.degree])),
        "degree_max": max(d for _, d in L.degree),
    }

    # Weighted centralities use the z-score as strength; path-based ones use hops, since a high z
    # means closeness and turning it into a distance would add another arbitrary choice.
    core = nx.core_number(L)
    cent = pd.DataFrame({
        "degree": nx.degree_centrality(L), "strength": dict(L.degree(weight="weight")),
        "betweenness": nx.betweenness_centrality(L), "closeness": nx.closeness_centrality(L),
        "eigenvector": nx.eigenvector_centrality_numpy(L, weight="weight"),
        "pagerank": nx.pagerank(L, alpha=0.85, weight="weight"), "core": core})

    runs = [gl.louvain(L, s) for s in range(LOUVAIN_RUNS)]
    Q = [nx.community.modularity(L, c, weight="weight") for c in runs]
    best = runs[int(np.argmax(Q))]
    # Numbered by size, so that labels are stable across re-runs
    best = sorted(best, key=len, reverse=True)
    part = gl.as_labels(best)
    nodes = list(L)
    stats.update(louvain_k=len(best), louvain_q=max(Q), louvain_q_mean=float(np.mean(Q)), louvain_q_std=float(np.std(Q)))
    pairs = [adjusted_rand_score([gl.as_labels(a)[n] for n in nodes], [gl.as_labels(b)[n] for n in nodes])
             for i, a in enumerate(runs) for b in runs[i + 1:]]
    stats["louvain_seed_ari"] = float(np.mean(pairs))
    levels = list(nx.community.louvain_partitions(L, weight="weight", seed=SEED))
    stats["louvain_hierarchy_k"] = [len(x) for x in levels]

    lpa_runs = [list(nx.community.asyn_lpa_communities(L, weight="weight", seed=s)) for s in range(LOUVAIN_RUNS)]
    lpa_q = [nx.community.modularity(L, c, weight="weight") for c in lpa_runs]
    lpa = lpa_runs[int(np.argmax(lpa_q))]
    lpa_part = gl.as_labels(lpa)
    stats.update(lpa_k=len(lpa), lpa_q=max(lpa_q), lpa_largest=max(map(len, lpa)),
                 lpa_vs_louvain_ari=adjusted_rand_score([lpa_part[n] for n in nodes], [part[n] for n in nodes]))

    # Null model: same degrees, random wiring
    null_q = []
    for s in range(20):
        R = nx.Graph(L.edges)
        nx.double_edge_swap(R, nswap=5 * R.number_of_edges(), max_tries=50 * R.number_of_edges(), seed=s)
        null_q.append(nx.community.modularity(R, nx.community.louvain_communities(R, seed=s)))
    stats.update(rewired_q_mean=float(np.mean(null_q)), rewired_q_std=float(np.std(null_q)))

    u = uni.loc[nodes].copy()
    u["community"] = pd.Series(part)
    u["holders"] = holders.reindex(nodes)
    u["size_tier"] = pd.qcut(uni["value"].rank(method="first"), 5, labels=False).reindex(nodes)
    pl = u["community"].tolist()
    rows = []
    for lab in ("ff12", "ff48", "sic2", "size_tier"):
        nmi, ari, nmi_null = compare(u[lab].astype(str).tolist(), pl)
        groups = [set(g.index) for _, g in u.groupby(lab)]
        rows.append({"labelling": lab, "groups": len(groups), "nmi_vs_louvain": nmi, "ari_vs_louvain": ari,
                     "nmi_shuffled": nmi_null, "modularity_of_labelling": round(nx.community.modularity(L, groups, weight="weight"), 3)})
    pd.DataFrame(rows).to_csv(RESULTS / "partition_comparison.csv", index=False)
    print(pd.DataFrame(rows).to_string(index=False))

    # Community description, including which managers are most over-represented
    mgr_names = pd.read_parquet(gl.INTERIM / f"managers_{MAIN_QUARTER}.parquet").drop_duplicates("CIK").set_index("CIK")["FILINGMANAGER_NAME"]
    pc = p[p["ISSUER"].isin(nodes)].assign(community=lambda d: d["ISSUER"].map(part))
    share_all = pc.groupby("CIK").size() / len(pc)
    summary, manager_rows = [], []
    for c, g in u.groupby("community"):
        g = g.sort_values("value", ascending=False)
        ff = Counter(g["ff12"]).most_common(3)
        internal = L.subgraph(g.index).number_of_edges()
        boundary = sum(1 for a, b in L.edges(g.index) if (a in g.index) != (b in g.index))
        summary.append({"community": c, "size": len(g), "top_ff12": ff, "ff12_purity": round(ff[0][1] / len(g), 3),
                        "top_sic": Counter(g["sic_desc"]).most_common(3), "median_value_pct": round(float(uni["value"].rank(pct=True).reindex(g.index).median()), 3),
                        "median_holders": float(g["holders"].median()), "value_bn": round(g["value"].sum() / 1e9, 1),
                        "conductance": round(boundary / max(2 * internal + boundary, 1), 3),
                        "top_names": list(g["NAME"].head(10))})
        in_c = pc[pc["community"] == c].groupby("CIK").size()
        lift = ((in_c / len(pc[pc["community"] == c])) / share_all.reindex(in_c.index)).rename("lift")
        best_m = pd.DataFrame({"lift": lift, "positions": in_c})
        best_m = best_m[best_m["positions"] >= max(5, 0.1 * len(g))].sort_values("lift", ascending=False).head(8)
        for cik, r in best_m.iterrows():
            manager_rows.append({"community": c, "manager": mgr_names.get(cik), "lift": round(r["lift"], 2), "positions": int(r["positions"])})
    pd.DataFrame(summary).to_csv(RESULTS / "community_summary.csv", index=False)
    pd.DataFrame(manager_rows).to_csv(RESULTS / "community_managers.csv", index=False)
    for s in summary:
        print(s)
    print(pd.DataFrame(manager_rows).groupby("community").head(4).to_string(index=False))

    # Share of a node's edges reaching other communities: 0 inside a community, near 1 for a bridge
    cent["community"] = pd.Series(part)
    cent["external_edge_share"] = [np.mean([part[v] != part[n] for v in L[n]]) for n in cent.index]
    cent = cent.join(u[["NAME", "ticker", "ff12", "ff48", "sic_desc", "value", "holders"]])
    cent["log_value"] = np.log(cent["value"])
    cent["log_holders"] = np.log(cent["holders"])
    cent.sort_values("pagerank", ascending=False).to_csv(RESULTS / "centrality.csv")
    metric_cols = ["degree", "strength", "betweenness", "closeness", "eigenvector", "pagerank", "core", "log_value", "log_holders"]
    corr = cent[metric_cols].corr(method="spearman").round(3)
    corr.to_csv(RESULTS / "centrality_correlations.csv")
    print(corr.to_string())
    for col in ("degree", "strength", "betweenness", "closeness", "eigenvector", "pagerank"):
        print(col, cent.nlargest(8, col)["NAME"].str[:20].tolist())
    print("bridges (top betweenness, external share):", cent.nlargest(10, "betweenness")[["NAME", "external_edge_share"]].round(2).values.tolist())

    u[["NAME", "ticker", "ff12", "ff48", "sic", "community", "value", "holders"]].to_csv(RESULTS / "communities.csv")
    nx.write_graphml(L, RESULTS / f"backbone_{MAIN_QUARTER}.graphml")
    (RESULTS / "graph_stats.json").write_text(json.dumps(stats, indent=1, default=float))
    print(json.dumps(stats, indent=1, default=float))


if __name__ == "__main__":
    main()
