"""Graph construction shared by all analysis steps.

Model: bipartite manager-issuer graph -> issuer projection -> statistically filtered backbone.
Nodes are issuers (first six CUSIP characters, which merges share classes of one company). An edge
means two issuers share significantly more holders than their popularity alone would produce.
"""
import numpy as np
import pandas as pd
import scipy.sparse as sp
import networkx as nx

from config import INTERIM, N_ISSUERS


def issuer_map():
    return pd.read_parquet(INTERIM / "issuer_map.parquet").set_index("ISSUER")


def load_positions(quarter):
    """One row per manager-issuer pair, with reported value summed across share classes."""
    h = pd.read_parquet(INTERIM / f"holdings_{quarter}.parquet", columns=["CIK", "CUSIP", "VALUE"])
    h["ISSUER"] = h["CUSIP"].str[:6]
    return h.groupby(["CIK", "ISSUER"], as_index=False)["VALUE"].sum()


def universe(positions, imap, n=N_ISSUERS):
    """Largest operating companies by total reported value in this quarter."""
    total = positions.groupby("ISSUER")["VALUE"].sum().sort_values(ascending=False)
    operating = imap.index[imap["operating"]]
    total = total[total.index.isin(operating)].head(n)
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
