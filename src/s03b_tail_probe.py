"""Step 3b: why are the z-scores heavy in both tails, and what does each backbone rule give?

1. Parametric bootstrap: draw bipartite graphs from the fitted model itself and score them the same way.
   If the model is right, about 0.3% of pairs fall beyond |z| > 3. If they do, the heavy tails in the real data
   are real structure; if they do not, the variance formula is too small.
2. Mean z by stock-size tier and by sector: which kinds of pair are over- or under-shared.
3. Backbone options on the real data: size, connectivity and agreement with sectors.
Output: results/tail_probe.csv, results/backbone_options.csv
"""
import networkx as nx
import numpy as np
import pandas as pd
from sklearn.metrics import normalized_mutual_info_score

import gutils as gl
from config import MAIN_QUARTER, N_ISSUERS, RESULTS, SEED

pd.set_option("display.width", 220, "display.max_colwidth", 40)


def main():
    imap = gl.issuer_map()
    pos = gl.load_positions(MAIN_QUARTER)
    uni = gl.universe(pos, imap, N_ISSUERS)
    p = pos[pos["ISSUER"].isin(uni.index)][["CIK", "ISSUER"]]
    fit = gl.shared_holder_z_bicm(p, uni)
    z, C, E, var, P, k = fit["z"], fit["C"], fit["expected"], fit["var"], fit["P"], fit["k"]
    N = len(uni)
    iu = np.triu_indices(N, 1)
    names = uni["NAME"].to_numpy()

    rng = np.random.default_rng(SEED)
    rows = [{"what": "real data", "share z>3 (%)": (z[iu] > 3).mean() * 100, "share z<-3 (%)": (z[iu] < -3).mean() * 100, "sd of z": z[iu].std()}]
    for r in range(3):
        Xs = (rng.random(P.shape) < P).astype(float)
        zs = (Xs @ Xs.T - E) / np.sqrt(var)
        rows.append({"what": f"simulated from the model, draw {r + 1}", "share z>3 (%)": (zs[iu] > 3).mean() * 100,
                     "share z<-3 (%)": (zs[iu] < -3).mean() * 100, "sd of z": zs[iu].std()})
    boot = pd.DataFrame(rows).round(2)
    print(boot.to_string(index=False))

    tier = pd.qcut(uni["value"].rank(method="first"), 5, labels=False).to_numpy()
    mat = np.zeros((5, 5))
    for a in range(5):
        for b in range(5):
            sel = ((tier[iu[0]] == a) & (tier[iu[1]] == b)) | ((tier[iu[0]] == b) & (tier[iu[1]] == a))
            mat[a, b] = z[iu][sel].mean()
    print("\nMean z by value tier of the two stocks (0 = smallest fifth by value, 4 = largest fifth):")
    print(pd.DataFrame(mat, columns=[f"tier {i}" for i in range(5)], index=[f"tier {i}" for i in range(5)]).round(1).to_string())
    sector = uni["ff12"].to_numpy()
    same = sector[iu[0]] == sector[iu[1]]
    zi = z[iu]
    print(f"\nSame sector: mean z {zi[same].mean():.1f}, z>3 {(zi[same] > 3).mean() * 100:.0f}%, z<-3 {(zi[same] < -3).mean() * 100:.0f}%")
    print(f"Different sector: mean z {zi[~same].mean():.1f}, z>3 {(zi[~same] > 3).mean() * 100:.0f}%, z<-3 {(zi[~same] < -3).mean() * 100:.0f}%")
    same_tier = tier[iu[0]] == tier[iu[1]]
    print(f"Same tier: mean z {zi[same_tier].mean():.1f}, z<-3 {(zi[same_tier] < -3).mean() * 100:.0f}%; different tier: mean z {zi[~same_tier].mean():.1f}, z<-3 {(zi[~same_tier] < -3).mean() * 100:.0f}%")
    for label, order in (("most negative", np.argsort(zi)[:6]), ("most positive", np.argsort(-zi)[:6])):
        print(f"{label}:", [(names[iu[0][i]][:14], names[iu[1][i]][:14], round(float(zi[i]), 1)) for i in order])
    pd.concat([boot.assign(table="bootstrap")]).to_csv(RESULTS / "tail_probe.csv", index=False)

    ff12 = uni["ff12"].tolist()
    out = []
    options = [("global z>3", "global", 0, 3.0), ("global z>10", "global", 0, 10.0), ("global z>20", "global", 0, 20.0),
               ("global z>30", "global", 0, 30.0), ("top-10 per stock (z>3)", "knn", 10, 3.0),
               ("top-15 per stock (z>3)", "knn", 15, 3.0), ("top-25 per stock (z>3)", "knn", 25, 3.0)]
    for label, method, top_k, z_min in options:
        G = gl.backbone(z, C, list(uni.index), method, top_k, z_min)
        comps = sorted(nx.connected_components(G), key=len, reverse=True)
        L = G.subgraph(comps[0]).copy()
        row = {"option": label, "edges": G.number_of_edges(), "mean degree": round(2 * G.number_of_edges() / N, 1),
               "isolated stocks": sum(1 for c in comps if len(c) == 1), "components": len(comps), "largest component": len(L)}
        if len(L) > 2 and L.number_of_edges() > 0:
            parts = [nx.community.louvain_communities(L, weight="weight", seed=s) for s in range(3)]
            qs = [nx.community.modularity(L, c, weight="weight") for c in parts]
            best = parts[int(np.argmax(qs))]
            lab = gl.as_labels(best)
            nodes = list(L)
            idx = {c: i for i, c in enumerate(uni.index)}
            row.update({"communities": len(best), "modularity": round(max(qs), 3),
                        "NMI vs sectors": round(normalized_mutual_info_score([ff12[idx[c]] for c in nodes], [lab[c] for c in nodes]), 3),
                        "degree vs holders (spearman)": round(pd.Series(dict(L.degree)).corr(pd.Series({c: k[idx[c]] for c in nodes}), method="spearman"), 3),
                        "diameter": nx.diameter(L) if len(L) <= 1200 else None})
        out.append(row)
        print(row, flush=True)
    pd.DataFrame(out).to_csv(RESULTS / "backbone_options.csv", index=False)
    print(pd.DataFrame(out).to_string(index=False))


if __name__ == "__main__":
    main()
