"""Build CSVs for a small Neo4j demo of the conviction graph (investor "tribes"), for the oral defense.

Exploration/demo only -- NOT part of the graded pipeline (s01-s04, regimes/*). Does not touch data/ or
results/. Recomputes, for two quarters only (2022Q2 and 2026Q2), the same conviction graph described in
src/regimes/conviction_build.py and the same tribe-profiling logic as src/regimes/conviction_profiles.py
(identical formulas and parameters), because the intermediate graphs_conviction/*.parquet files those
scripts write are regenerable caches (gitignored, not persisted on this machine) -- there was nothing to
load, so this script rebuilds just enough of them to get full tribe membership and the actual edges.

Story (agreed with the team): the "merger arbitrage" tribe -- a handful of funds (Gabelli, Millennium,
Verition, Pentwater, Prelude...) betting on takeover targets -- holds completely different stocks in
2022Q2 (Activision, VMware, Twitter, Citrix...) than in 2026Q2 (Warner Bros Discovery, EA, Chart
Industries...), yet keeps the same bettors. No official sector groups these stocks; the conviction graph
does, from the overweight pattern alone.

Output (neo4j/export/):
  stocks.csv     one row per stock across both quarters (issuer, name, ticker, ff12 sector, quarter, tribe,
                 tribe_name, participation (bridge score), degree, strength, value_bn)
  managers.csv   one row per manager appearing in a BETS_ON edge below (cik, name)
  tribes.csv     one row per (quarter, tribe) with a human label and size
  co_bet.csv     stock-stock edges within the selected stocks (z-score, shared bettors), by quarter
  bets_on.csv    manager-stock overweight edges, restricted to each tribe's top bettors

Usage: python neo4j/build_demo_data.py
"""
import sys
from pathlib import Path

import networkx as nx
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import gutils as gl  # noqa: E402
from config import INTERIM, ISSUER_ALIASES, N_ISSUERS  # noqa: E402

OUT = Path(__file__).resolve().parent / "export"
OUT.mkdir(parents=True, exist_ok=True)

# Same parameters as src/regimes/conviction_build.py
MAIN_T, MIN_POS, MIN_BETTORS, TOP_K, Z_MIN, RUNS, SEED = 2.0, 10, 5, 15, 3.0, 20, 42
QUARTERS = ["2022Q2", "2026Q2"]

# Tribes worth a human name for the demo (by quarter, 1-indexed, biggest community first).
# Assigned by reading each group's top-by-value members and FF48 mix (see neo4j/NOTES.md); not guessed.
TRIBE_NAMES = {
    ("2022Q2", 1): "Diversified large-cap",
    ("2022Q2", 2): "Industrials & aerospace",
    ("2022Q2", 3): "Mega-cap tech",
    ("2022Q2", 4): "Healthcare & industrial tech",
    ("2022Q2", 5): "Energy & managed care",
    ("2022Q2", 6): "Blue-chip dividend",
    ("2022Q2", 7): "Income REITs",
    ("2022Q2", 8): "ADRs & global tech",
    ("2022Q2", 9): "Canadian home bias",
    ("2022Q2", 10): "Merger arbitrage",
    ("2026Q2", 1): "Diversified large-cap",
    ("2026Q2", 2): "Mega-cap tech & blue chip",
    ("2026Q2", 3): "Industrials & insurance",
    ("2026Q2", 4): "AI hardware & semis",
    ("2026Q2", 5): "ADRs & global tech",
    ("2026Q2", 6): "Income REITs",
    ("2026Q2", 7): "Canadian home bias",
    ("2026Q2", 8): "Biotech / clinical-stage",
    ("2026Q2", 9): "Merger arbitrage",
    ("2026Q2", 10): "Midstream & private markets",
}


def bets_for_quarter(q, uni):
    h = pd.read_parquet(INTERIM / f"holdings_{q}.parquet", columns=["CIK", "CUSIP", "VALUE", "VALUE_RELIABLE"])
    h["ISSUER"] = h["CUSIP"].str[:6].replace(ISSUER_ALIASES)
    pos = h.groupby(["CIK", "ISSUER"], as_index=False).agg(VALUE=("VALUE", "sum"), REL=("VALUE_RELIABLE", "all"))
    p = pos[pos["ISSUER"].isin(uni.index) & pos["REL"] & (pos["VALUE"] > 0)].copy()
    p = p[p.groupby("CIK")["ISSUER"].transform("size") >= MIN_POS]
    mkt = p.groupby("ISSUER")["VALUE"].sum()
    mkt = mkt / mkt.sum()
    p["w"] = p["VALUE"] / p.groupby("CIK")["VALUE"].transform("sum")
    p["W"] = p["ISSUER"].map(mkt)
    p["ow"] = p["w"] / (p["W"] / p.groupby("CIK")["W"].transform("sum"))
    return p


def participation(H, labels):
    """1 - sum_c (k_ic / k_i)^2 : 0 if all of a stock's links stay inside its own tribe."""
    out = {}
    for v in H:
        if H.degree(v) == 0:
            out[v] = 0.0
            continue
        counts = {}
        for u in H[v]:
            counts[labels[u]] = counts.get(labels[u], 0) + 1
        out[v] = 1 - sum((c / H.degree(v)) ** 2 for c in counts.values())
    return out


def build_quarter(q):
    print(f"\n=== {q} ===", flush=True)
    imap = gl.issuer_map()
    pos = gl.load_positions(q)
    uni = gl.universe(pos, imap, N_ISSUERS)
    p = bets_for_quarter(q, uni)

    b = p[p["ow"] > MAIN_T][["CIK", "ISSUER"]]
    bettors = b.groupby("ISSUER")["CIK"].nunique()
    keep = bettors[bettors >= MIN_BETTORS].index
    u = uni.loc[uni.index.isin(keep)].copy()
    b = b[b["ISSUER"].isin(u.index)]

    fit = gl.shared_holder_z_bicm(b, u)
    names = list(u.index)
    G = gl.backbone(fit["z"], fit["C"], names, "knn", TOP_K, Z_MIN)
    u = u.assign(bettors=fit["k"])

    H = G.subgraph([v for v in G if G.degree(v) > 0]).copy()
    runs = [nx.community.louvain_communities(H, weight="weight", seed=SEED + s) for s in range(RUNS)]
    best = max(runs, key=lambda c: nx.community.modularity(H, c, weight="weight"))
    comms = sorted(best, key=len, reverse=True)
    labels = {v: i + 1 for i, c in enumerate(comms) for v in c}
    part = participation(H, labels)

    print(f"stocks in universe {len(u)}, bets {len(b)}, linked stocks {H.number_of_nodes()}, "
          f"edges {G.number_of_edges()}, communities {len(comms)} (sizes {[len(c) for c in comms[:12]]})")
    return dict(u=u, p=p, G=G, H=H, comms=comms, labels=labels, part=part)


data = {q: build_quarter(q) for q in QUARTERS}

# ---- find the merger-arbitrage tribe in each quarter by a known ticker ----
MERGER_ARB_GROUP = {}
for q, marker_name in [("2022Q2", "ACTIVISION"), ("2026Q2", "WARNER BROS")]:
    u = data[q]["u"]
    issuer = u[u["NAME"].str.contains(marker_name, case=False, na=False)].index[0]
    MERGER_ARB_GROUP[q] = data[q]["labels"][issuer]

mnames = {q: pd.read_parquet(INTERIM / f"managers_{q}.parquet").drop_duplicates("CIK").set_index("CIK")["FILINGMANAGER_NAME"]
          for q in QUARTERS}


def top_bettors_in(q, members, n=6):
    p = data[q]["p"]
    bets = p[(p["ow"] > MAIN_T) & (p["ISSUER"].isin(members))]
    return bets.groupby("CIK")["ISSUER"].nunique().sort_values(ascending=False).head(n)


def strength_in_group(H, members):
    members = set(members)
    return {v: sum(d["weight"] for u, d in H[v].items() if u in members) for v in members}


# ---------------------------------------------------------------------------------------
# Decide which stocks to load, per quarter:
#  - merger-arb tribe: ALL its members (scenes 1, 2, 4)
#  - 2026Q2 only: top 10 stocks (by in-tribe strength) of every other named tribe (scene 3)
# ---------------------------------------------------------------------------------------
selected = {q: set() for q in QUARTERS}
tribe_of = {}       # (q, issuer) -> group number
for q in QUARTERS:
    g = MERGER_ARB_GROUP[q]
    members = set(data[q]["comms"][g - 1])
    selected[q] |= members
    for v in members:
        tribe_of[(q, v)] = g
    # also load any stock a tribe member is linked to (its top-15 backbone neighbours), even if that
    # neighbour's own community lies elsewhere -- so scene 2 (click one stock, show all its links)
    # never points at a node that isn't loaded
    G = data[q]["G"]
    neighbours = set().union(*(set(G[v]) for v in members)) - members
    for v in neighbours:
        tribe_of[(q, v)] = data[q]["labels"].get(v, 0)
    selected[q] |= neighbours

q26 = "2026Q2"
scene3_rank = {}   # (q, issuer) -> 1..10, only for the stocks picked to represent a tribe in scene 3
for i, c in enumerate(data[q26]["comms"], start=1):
    if len(c) < 10:
        continue
    strength = strength_in_group(data[q26]["H"], c)
    top10 = sorted(c, key=lambda v: -strength.get(v, 0))[:10]
    selected[q26] |= set(top10)
    for rank, v in enumerate(top10, start=1):
        tribe_of[(q26, v)] = i
        scene3_rank[(q26, v)] = rank

print("\nSelected stock counts:", {q: len(selected[q]) for q in QUARTERS})

# ---- node tables ----
stock_rows, manager_rows, tribe_rows, co_bet_rows, bets_on_rows = [], [], {}, [], []
manager_seen = {}

for q in QUARTERS:
    u, H, part = data[q]["u"], data[q]["H"], data[q]["part"]
    for v in sorted(selected[q]):
        row = u.loc[v]
        g = tribe_of[(q, v)]
        stock_rows.append({
            "stockId": f"{q}_{v}", "quarter": q, "issuer": v,
            "name": row["NAME"], "ticker": row["ticker"] if pd.notna(row["ticker"]) else "",
            "sector": row["ff12"] if pd.notna(row["ff12"]) else "Other",
            "tribeId": f"{q}_G{g}", "value_bn": round(row["value"] / 1e9, 2),
            "bettors": int(row["bettors"]), "participation": round(part.get(v, 0.0), 3),
            "sceneRank": scene3_rank.get((q, v), ""),
        })
    for g in sorted({tribe_of[(q, v)] for v in selected[q]}):
        label = TRIBE_NAMES.get((q, g), f"Group {g}")
        tribe_rows[f"{q}_G{g}"] = {"tribeId": f"{q}_G{g}", "quarter": q, "groupNum": g,
                                    "name": label, "size_full": len(data[q]["comms"][g - 1])}

    # CO_BET: edges of the full backbone graph G with both endpoints selected
    G = data[q]["G"]
    sel = selected[q]
    for a, b, d in G.edges(data=True):
        if a in sel and b in sel:
            co_bet_rows.append({"quarter": q, "source": f"{q}_{a}", "target": f"{q}_{b}",
                                 "z": round(d["weight"], 2), "shared": d["shared"]})

    # BETS_ON: top bettors of the merger-arb tribe only (keeps the manager count small, per the brief)
    g_arb = MERGER_ARB_GROUP[q]
    members = data[q]["comms"][g_arb - 1]
    top_mgr = top_bettors_in(q, members, n=6)
    p = data[q]["p"]
    bets = p[(p["ow"] > MAIN_T) & (p["CIK"].isin(top_mgr.index)) & (p["ISSUER"].isin(members))]
    for _, r in bets.iterrows():
        cik = r["CIK"]
        if cik not in manager_seen:
            manager_seen[cik] = str(mnames[q].get(cik, cik))
            manager_rows.append({"managerId": cik, "name": manager_seen[cik]})
        bets_on_rows.append({"managerId": cik, "stockId": f"{q}_{r['ISSUER']}", "quarter": q,
                              "overweight": round(r["ow"], 2)})

stocks = pd.DataFrame(stock_rows)
tribes = pd.DataFrame(list(tribe_rows.values()))
managers = pd.DataFrame(manager_rows)
co_bet = pd.DataFrame(co_bet_rows)
bets_on = pd.DataFrame(bets_on_rows)

for name, df in [("stocks", stocks), ("tribes", tribes), ("managers", managers),
                  ("co_bet", co_bet), ("bets_on", bets_on)]:
    df.to_csv(OUT / f"{name}.csv", index=False)
    print(f"{name}.csv: {len(df)} rows")

print("\nManagers used (BETS_ON):")
print(managers.to_string(index=False))
print("\nMerger-arb tribes, quarter -> size selected:")
for q in QUARTERS:
    g = MERGER_ARB_GROUP[q]
    print(f"  {q} group {g} ({TRIBE_NAMES.get((q, g))}): {(stocks.quarter == q).sum()} stocks loaded, "
          f"{len(data[q]['comms'][g - 1])} in full tribe")
print("\nBridge stocks (2026Q2 subgraph, participation):")
print(stocks[stocks.quarter == "2026Q2"].sort_values("participation", ascending=False).head(8)
      [["name", "ticker", "sector", "tribeId", "participation"]].to_string(index=False))

# EA's neighbours, for scene 2 -- check whether any lie outside the loaded node set
ea = data["2026Q2"]["u"][data["2026Q2"]["u"]["NAME"].str.contains("ELECTRONIC ARTS")].index[0]
G26 = data["2026Q2"]["G"]
print(f"\nElectronic Arts ({ea}) neighbours in the full 2026Q2 backbone:")
for nb, d in sorted(G26[ea].items(), key=lambda kv: -kv[1]["weight"]):
    flag = "" if nb in selected["2026Q2"] else "  <-- NOT in loaded node set"
    name = data["2026Q2"]["u"].loc[nb, "NAME"]
    print(f"  z={d['weight']:.1f} shared={d['shared']:<3} {name}{flag}")
