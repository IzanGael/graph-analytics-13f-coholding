"""Regime tests on the conviction graph, and comparison with the ownership graph.

Inputs: conviction/conviction_runs_t<thr>.pkl (conviction_build.py), calendar_similarity_matrix.csv (investor_calendar.py,
ownership), the repo graphs (nodes/edges per quarter).
Tests (same as for ownership):
  B  consecutive quarters: ARI at the 5 macro boundaries vs the 13 other transitions (exact permutation test)
  C  all quarter pairs: same macro regime vs different regime at equal time gap (null = all boundary placements)
  D  investor calendar: best contiguous cuts vs a smooth-drift null
  E  break strength per transition vs smooth-drift null; macro boundaries vs others
Comparison: drift curves, break strength side by side, same-quarter ARI ownership vs conviction, NMI with sectors and
with size quintiles (size control).
Usage: python conviction_analysis.py <repo folder> <folder with inputs and outputs>
"""
import itertools, pickle, sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import pandas as pd
from sklearn.metrics import adjusted_rand_score as ari, normalized_mutual_info_score as nmi

REPO, D = Path(sys.argv[1]), Path(sys.argv[2])
CD = D / "conviction"
GDIR = REPO / "data" / "interim" / "graphs"
MACRO = [("2021Q4", "2022Q3", "Repricing"), ("2022Q4", "2023Q2", "Disinflation"), ("2023Q3", "2024Q4", "AI soft landing"),
         ("2025Q1", "2025Q2", "Tariff shock"), ("2025Q3", "2025Q4", "Boom + soft labor"), ("2026Q1", "2026Q2", "Energy shock")]
Q = [f"{y}Q{q}" for y in range(2021, 2027) for q in range(1, 5) if "2021Q4" <= f"{y}Q{q}" <= "2026Q2"]
n, WIN, rng = len(Q), 2, np.random.default_rng(42)
reg = np.array([next(i for i, (a, b, _) in enumerate(MACRO) if a <= q <= b) for q in Q])
mcuts = [i for i in range(1, n) if reg[i] != reg[i - 1]]
OWN_BLUE, CONV_ORANGE = "#4a6fa5", "#d9480f"


def sim_matrix(runs, nruns):
    S = np.zeros((n, n))
    for i in range(n):
        for j in range(i, n):
            A, B = runs[Q[i]][:nruns], runs[Q[j]][:nruns]
            common = sorted(set(A[0]) & set(B[0]))
            pairs = itertools.combinations(A, 2) if i == j else itertools.product(A, B)
            S[i, j] = S[j, i] = np.mean([ari([x[v] for v in common], [y[v] for v in common]) for x, y in pairs])
    return S


def drift_null(S, draws):
    lag = {d: np.mean([S[i, i + d] for i in range(n - d)]) for d in range(1, n)}
    for _ in range(draws):
        N = S.copy()
        for d in range(1, n):
            r = np.array([S[i, i + d] - lag[d] for i in range(n - d)]); rng.shuffle(r)
            for i in range(n - d):
                N[i, i + d] = N[i + d, i] = lag[d] + r[i]
        yield N


def strengths(M):
    out = []
    for c in range(1, n):
        L, R = list(range(max(0, c - WIN), c)), list(range(c, min(n, c + WIN)))
        w = [M[i, j] for g in (L, R) for i, j in itertools.combinations(g, 2)]
        out.append(np.mean(w) - np.mean([M[i, j] for i in L for j in R]))
    return np.array(out)


def seg_explained(M, kmax=6):
    def cost(a, b):
        m = b - a
        return 0.0 if m < 2 else float((1 - M[a:b, a:b])[np.triu_indices(m, 1)].sum() / m)
    C = [[cost(a, b) if b > a else np.inf for b in range(n + 1)] for a in range(n + 1)]
    best = np.full((kmax + 1, n + 1), np.inf); arg = np.zeros((kmax + 1, n + 1), int); best[0, 0] = 0
    for k in range(1, kmax + 1):
        for b in range(1, n + 1):
            v = [best[k - 1, a] + C[a][b] for a in range(b)]; arg[k, b] = int(np.argmin(v)); best[k, b] = v[arg[k, b]]
    res = {}
    for k in range(2, kmax + 1):
        cuts, b = [], n
        for kk in range(k, 0, -1):
            a = arg[kk, b]
            if a > 0:
                cuts.append(a)
            b = a
        res[k] = (100 * (1 - best[k, n] / best[1, n]), sorted(cuts))
    return res


def regime_tests(S, label, draws=2000):
    out = {"graph": label}
    x = np.array([S[i, i + 1] for i in range(n - 1)]); b = np.array([i + 1 in mcuts for i in range(n - 1)])
    obs = x[~b].mean() - x[b].mean()
    null = [x[~m].mean() - x[m].mean() for c in itertools.combinations(range(n - 1), 5)
            for m in [np.isin(np.arange(n - 1), c)]]
    out.update(consec_inside=x[~b].mean(), consec_boundary=x[b].mean(), p_consec=np.mean(np.array(null) >= obs - 1e-12))

    def lag_gap(r):
        g = []
        for lag in range(1, 6):
            s = [S[i, i + lag] for i in range(n - lag) if r[i] == r[i + lag]]
            d = [S[i, i + lag] for i in range(n - lag) if r[i] != r[i + lag]]
            if s and d:
                g.append(np.mean(s) - np.mean(d))
        return np.mean(g)
    o2 = lag_gap(reg)
    n2 = [lag_gap(np.cumsum([i in c for i in range(n)])) for c in itertools.combinations(range(1, n), 5)]
    out.update(same_minus_diff_regime=o2, p_equal_lag=np.mean(np.array(n2) >= o2 - 1e-12))
    for d in (1, 4, 8, 12, 18):
        out[f"ari_gap_{d}q"] = np.mean([S[i, i + d] for i in range(n - d)])
    seg = seg_explained(S)
    nulls = list(drift_null(S, draws))
    nseg = [seg_explained(N) for N in nulls]
    nstr = np.array([strengths(N) for N in nulls])
    for k in (3, 5, 6):
        out[f"seg{k}_cuts"] = ", ".join(Q[c] for c in seg[k][1])
        out[f"seg{k}_p_vs_drift"] = np.mean([ns[k][0] >= seg[k][0] - 1e-12 for ns in nseg])
    st = strengths(S)
    brk = pd.DataFrame({"to": Q[1:], "break_strength": st, "macro_boundary": [c in mcuts for c in range(1, n)],
                        "p_vs_drift": [(nstr[:, k] >= st[k]).mean() for k in range(n - 1)]})
    m = brk.macro_boundary.values
    o3 = st[m].mean() - st[~m].mean()
    n3 = [st[list(c)].mean() - np.delete(st, list(c)).mean() for c in itertools.combinations(range(n - 1), 5)]
    out.update(break_macro=st[m].mean(), break_other=st[~m].mean(), p_break_macro=np.mean(np.array(n3) >= o3 - 1e-12))
    return out, brk


# Similarity matrices
own = pd.read_csv(D / "calendar_similarity_matrix.csv", index_col=0).loc[Q, Q].values
conv = {}
for t, nr in ((2.0, 20), (1.5, 6), (3.0, 6)):
    with open(CD / f"conviction_runs_t{t}.pkl", "rb") as f:
        runs = pickle.load(f)
    conv[t] = sim_matrix(runs, nr)
    pd.DataFrame(conv[t], index=Q, columns=Q).round(3).to_csv(CD / f"conviction_similarity_t{t}.csv")
    print("matrix", t, flush=True)
    if t == 2.0:
        main_runs = runs

rows, brks = [], {}
for label, S in (("ownership", own), ("conviction t2.0", conv[2.0]), ("conviction t1.5", conv[1.5]), ("conviction t3.0", conv[3.0])):
    r, b = regime_tests(S, label, draws=2000 if label in ("ownership", "conviction t2.0") else 500)
    rows.append(r); brks[label] = b
    print(label, "tested", flush=True)
tests = pd.DataFrame(rows)
tests.round(3).to_csv(CD / "regime_tests_ownership_vs_conviction.csv", index=False)
pd.set_option("display.width", 250)
print(tests.round(3).T.to_string())
cb = brks["conviction t2.0"].merge(brks["ownership"][["to", "break_strength", "p_vs_drift"]], on="to", suffixes=("_conv", "_own"))
cb.round(4).to_csv(CD / "break_strength_ownership_vs_conviction.csv", index=False)
print(cb.round(3).sort_values("break_strength_conv", ascending=False).to_string(index=False))

# Same-quarter comparison and size control
comp = []
for q in Q:
    nodes = pd.read_parquet(GDIR / f"nodes_{q}.parquet")
    size_q = pd.qcut(nodes["value"].rank(method="first"), 5, labels=False)
    e = pd.read_parquet(GDIR / f"edges_k15_{q}.parquet")
    G = nx.Graph(); G.add_weighted_edges_from(e[["source", "target", "z"]].itertuples(index=False))
    own_runs = [nx.community.louvain_communities(G, weight="weight", seed=42 + s) for s in range(5)]
    own_best = max(own_runs, key=lambda c: nx.community.modularity(G, c, weight="weight"))
    ol = {v: i for i, c in enumerate(own_best) for v in c}
    cl = main_runs[q][0]
    common = sorted(set(ol) & set(cl))
    row = {"quarter": q, "stocks_in_both": len(common),
           "ari_own_vs_conv": ari([ol[v] for v in common], [cl[v] for v in common])}
    for name, lab in (("own", ol), ("conv", cl)):
        vs = sorted(lab)
        row[f"nmi_{name}_vs_ff12"] = nmi(nodes.loc[vs, "ff12"].fillna("NA"), [lab[v] for v in vs])
        row[f"nmi_{name}_vs_size"] = nmi(size_q.loc[vs], [lab[v] for v in vs])
    comp.append(row)
comp = pd.DataFrame(comp)
comp.round(3).to_csv(CD / "ownership_vs_conviction_per_quarter.csv", index=False)
print(comp.round(3).to_string(index=False))
print(comp.drop(columns="quarter").mean().round(3).to_string())

# Figures
fig, axes = plt.subplots(1, 2, figsize=(14, 6.2))
starts = [i for i in range(n) if i == 0 or reg[i] != reg[i - 1]] + [n]
for ax, S, title in ((axes[0], own, "Ownership graph (who holds what)"), (axes[1], conv[2.0], "Conviction graph (who bets on what)")):
    im = ax.imshow(S, cmap="Blues", vmin=0, vmax=1)
    ax.set_xticks(range(n), Q, rotation=90, fontsize=7); ax.set_yticks(range(n), Q, fontsize=7)
    for k in range(len(starts) - 1):
        a, e_ = starts[k] - 0.5, starts[k + 1] - 0.5
        ax.add_patch(plt.Rectangle((a, a), e_ - a, e_ - a, fill=False, ec=CONV_ORANGE, lw=1.8))
    for s in ax.spines.values():
        s.set_visible(False)
    ax.set_title(title, fontsize=11, loc="left")
fig.colorbar(im, ax=axes, fraction=0.025, pad=0.02).set_label("Group similarity between two quarters (ARI)", fontsize=9)
fig.suptitle("Do investor groups reorganise with macro regimes? Orange squares = macro regimes", x=0.02, ha="left", fontsize=12)
fig.savefig(CD / "heatmaps_ownership_vs_conviction.png", dpi=150, bbox_inches="tight")

fig, ax = plt.subplots(figsize=(11, 4.6))
xs = np.arange(n - 1)
ax.bar(xs - 0.2, cb["break_strength_own"], 0.38, color=OWN_BLUE, label="Ownership")
ax.bar(xs + 0.2, cb["break_strength_conv"], 0.38, color=CONV_ORANGE, label="Conviction")
for c in mcuts:
    ax.axvspan(c - 1 - 0.5, c - 1 + 0.5, color="#999", alpha=0.18, lw=0)
ax.set_xticks(xs, cb["to"], rotation=90, fontsize=8)
ax.set_ylabel("Break strength (higher = sharper change)")
ax.set_title("How sharply the groups change going into each quarter. Grey bands = macro regime boundaries", loc="left", fontsize=10)
ax.legend(frameon=False)
for s in ("top", "right"):
    ax.spines[s].set_visible(False)
fig.tight_layout(); fig.savefig(CD / "break_strength_ownership_vs_conviction.png", dpi=150)

fig, ax = plt.subplots(figsize=(7, 4.2))
for S, lab, col in ((own, "Ownership", OWN_BLUE), (conv[2.0], "Conviction", CONV_ORANGE)):
    ax.plot(range(1, n), [np.mean([S[i, i + d] for i in range(n - d)]) for d in range(1, n)], color=col, lw=2, marker="o", ms=4, label=lab)
ax.set_xlabel("Quarters apart"); ax.set_ylabel("Group similarity (ARI)"); ax.set_ylim(0, 1)
ax.set_title("How fast do the groups drift?", loc="left", fontsize=11); ax.legend(frameon=False)
for s in ("top", "right"):
    ax.spines[s].set_visible(False)
fig.tight_layout(); fig.savefig(CD / "drift_ownership_vs_conviction.png", dpi=150)
print("saved figures")
