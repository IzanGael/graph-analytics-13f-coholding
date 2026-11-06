"""Graph construction shared by all analysis steps.

Model: bipartite manager-issuer graph -> issuer projection -> statistically filtered backbone.
Nodes are issuers (first six CUSIP characters, which merges share classes of one company). An edge
means two issuers share significantly more holders than their popularity alone would produce.
"""
import numpy as np
import pandas as pd
import scipy.sparse as sp
import networkx as nx

from config import INTERIM, ISSUER_ALIASES, MIN_HOLDERS, N_ISSUERS


def issuer_map():
    return pd.read_parquet(INTERIM / "issuer_map.parquet").set_index("ISSUER")


def load_positions(quarter):
    """One row per manager-issuer pair, with reported value summed across share classes."""
    h = pd.read_parquet(INTERIM / f"holdings_{quarter}.parquet", columns=["CIK", "CUSIP", "VALUE", "VALUE_RELIABLE"])
    h["VALUE"] = h["VALUE"].where(h["VALUE_RELIABLE"], 0)   # inflated filers keep links, not value
    h["ISSUER"] = h["CUSIP"].str[:6].replace(ISSUER_ALIASES)
    return h.groupby(["CIK", "ISSUER"], as_index=False)["VALUE"].sum()


def universe(positions, imap, n=N_ISSUERS):
    """Largest operating companies by total reported value in this quarter, held by at least MIN_HOLDERS managers."""
    total = positions.groupby("ISSUER")["VALUE"].sum().sort_values(ascending=False)
    holders = positions.groupby("ISSUER")["CIK"].nunique()
    operating = imap.index[imap["operating"]]
    total = total[total.index.isin(operating) & (holders.reindex(total.index) >= MIN_HOLDERS)].head(n)
    u = imap.loc[total.index, ["NAME", "ticker", "sic", "sic2", "sic_desc", "ff12", "ff48"]].copy()
    u["value"] = total
    return u


def restrict_managers(positions, uni, low, high):
    """Keep managers with low..high positions inside the universe (None = no limit)."""
    p = positions[positions["ISSUER"].isin(uni.index)]
    size = p.groupby("CIK").size()
    keep = size[(size >= low) & (size <= (high if high is not None else size.max()))].index
    return p[p["CIK"].isin(keep)]


def shared_holder_z(p, uni):
    """Co-holding counts and their z-scores under independent holding (hypergeometric null).

    For issuers i, j with k_i, k_j holders among m managers, the count of shared holders has
    mean k_i k_j / m and variance k_i k_j (m - k_i)(m - k_j) / (m^2 (m - 1)).
    """
    managers = {c: i for i, c in enumerate(p["CIK"].unique())}
    issuers = {c: i for i, c in enumerate(uni.index)}
    X = sp.csr_matrix((np.ones(len(p)), (p["ISSUER"].map(issuers), p["CIK"].map(managers))),
                      shape=(len(issuers), len(managers)))
    C = (X @ X.T).toarray().astype(float)
    k = np.asarray(X.sum(axis=1)).ravel()
    m = len(managers)
    mean = np.outer(k, k) / m
    var = mean * np.outer(m - k, m - k) / (m * max(m - 1, 1))
    z = (C - mean) / np.sqrt(np.maximum(var, 1e-9))
    np.fill_diagonal(z, 0)
    np.fill_diagonal(C, 0)
    return C, z, k, m


def solve_bicm(k, n, iters=8000, tol=1e-9):
    """Bipartite configuration model: p_im = x_i y_m / (1 + x_i y_m) with x, y chosen so that the expected
    stock degrees equal k and the expected manager degrees equal n. Returns P, iterations, max degree errors.

    Managers with the same number of links share the same y, so the fixed-point iteration runs over the
    distinct manager sizes (a few hundred) instead of every manager (thousands): same answer, far faster.
    """
    if (k <= 0).any() or (n <= 0).any():
        raise ValueError("solve_bicm needs every stock and manager to have at least one link")
    levels, inverse, counts = np.unique(n, return_inverse=True, return_counts=True)
    levels = levels.astype(float)
    E = k.sum()
    x, y = k / np.sqrt(E), levels / np.sqrt(E)
    for it in range(iters):
        D = 1.0 + np.outer(x, y)
        x_new = k / ((counts * y)[None, :] / D).sum(axis=1)
        y_new = levels / (x[:, None] / D).sum(axis=0)
        gap = max(np.abs(x_new / x - 1).max(), np.abs(y_new / y - 1).max())
        x, y = x_new, y_new
        if gap < tol:
            break
    P = np.outer(x, y[inverse])
    P = P / (1.0 + P)
    return P, it + 1, float((np.abs(P.sum(axis=1) - k) / k).max()), float((np.abs(P.sum(axis=0) - n) / n).max())


def shared_holder_z_bicm(p, uni):
    """Co-holding counts and z-scores under a chance model that respects stock popularity AND manager size.

    Expected shared holders of i and j: sum_m p_im p_jm. Variance: sum_m q (1 - q) with q = p_im p_jm.
    Managers holding every stock are dropped: they add the same constant to every pair.
    """
    size = p.groupby("CIK").size()
    kept = size[size < len(uni)].index
    p = p[p["CIK"].isin(kept)]
    managers = {c: i for i, c in enumerate(p["CIK"].unique())}
    issuers = {c: i for i, c in enumerate(uni.index)}
    X = sp.csr_matrix((np.ones(len(p)), (p["ISSUER"].map(issuers), p["CIK"].map(managers))), shape=(len(issuers), len(managers)))
    k = np.asarray(X.sum(axis=1)).ravel()
    n = np.asarray(X.sum(axis=0)).ravel()
    C = (X @ X.T).toarray().astype(float)
    P, iters, err_k, err_n = solve_bicm(k, n)
    expected = P @ P.T
    P2 = P * P
    var = np.maximum(expected - P2 @ P2.T, 1e-9)
    z = (C - expected) / np.sqrt(var)
    for m in (C, expected, z):
        np.fill_diagonal(m, 0)
    return {"C": C, "z": z, "expected": expected, "var": var, "P": P, "k": k, "n": n, "X": X, "iterations": iters,
            "err_stock_degree": err_k, "err_manager_degree": err_n, "managers_dropped": int(len(size) - len(kept))}


def backbone(z, C, names, method="knn", top_k=15, z_min=3.0):
    """'knn': union of each node's top_k partners with z > z_min. 'global': all pairs with z > z_min."""
    G = nx.Graph()
    G.add_nodes_from(names)
    if method == "knn":
        order = np.argsort(-z, axis=1)[:, :top_k]
        pairs = ((i, int(j)) for i in range(len(names)) for j in order[i] if z[i, j] > z_min)
    else:
        rows, cols = np.where(np.triu(z, 1) > z_min)
        pairs = zip(rows.tolist(), cols.tolist())
    for i, j in pairs:
        G.add_edge(names[i], names[j], weight=float(z[i, j]), shared=int(C[i, j]))
    return G


def largest_component(G):
    return G.subgraph(max(nx.connected_components(G), key=len)).copy()


def louvain(G, seed):
    return nx.community.louvain_communities(G, weight="weight", seed=seed)


def as_labels(communities):
    return {n: i for i, c in enumerate(communities) for n in c}


def implied_prices(quarter):
    """Issuer price proxy: median value/shares across filers of its most-held share class."""
    h = pd.read_parquet(INTERIM / f"holdings_{quarter}.parquet", columns=["CUSIP", "VALUE", "SHARES"])
    h = h[h["SHARES"] > 0]
    h["ISSUER"] = h["CUSIP"].str[:6]
    h["P"] = h["VALUE"] / h["SHARES"]
    h["shares_total"] = h.groupby("CUSIP")["SHARES"].transform("sum")
    primary = h.sort_values("shares_total").drop_duplicates("ISSUER", keep="last").set_index("ISSUER")["CUSIP"]
    px = h.groupby("CUSIP")["P"].median()
    return px.reindex(primary.values).set_axis(primary.index), primary
