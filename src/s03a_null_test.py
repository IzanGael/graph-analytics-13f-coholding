"""Step 3a: test the size-aware chance expectation (bipartite configuration model) on one quarter.

Old null: independent holding given each stock's popularity only (hypergeometric).
New null: also respects each manager's portfolio size (see graphlib.shared_holder_z_bicm).
Output: figures/f7_null_calibration.png, results/null_test.csv
"""
import sys

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.ticker import FuncFormatter

import gutils as gl
from config import FIGURES, MAIN_QUARTER, N_ISSUERS, RESULTS

QUARTER = sys.argv[1] if len(sys.argv) > 1 else MAIN_QUARTER


def main():
    imap = gl.issuer_map()
    pos = gl.load_positions(QUARTER)
    uni = gl.universe(pos, imap, N_ISSUERS)
    p = pos[pos["ISSUER"].isin(uni.index)][["CIK", "ISSUER"]]
    new = gl.shared_holder_z_bicm(p, uni)
    C, z_full, k, n, X = new["C"], new["z"], new["k"], new["n"], new["X"]
    N, M = X.shape
    print(f"{QUARTER}: {N} stocks, {M:,} managers ({new['managers_dropped']} holding every stock dropped), {int(k.sum()):,} links")
    print(f"BiCM: {new['iterations']} iterations; max degree error: stocks {new['err_stock_degree']:.2e}, managers {new['err_manager_degree']:.2e}")

    # Old null, computed on exactly the same managers so the comparison is fair
    kept = p.groupby("CIK").size()
    p_kept = p[p["CIK"].isin(kept[kept < len(uni)].index)]
    _, z_old_full, _, _ = gl.shared_holder_z(p_kept, uni)
    E_old_full = np.outer(k, k) / M

    iu = np.triu_indices(N, 1)
    obs, e_old, e_new, zo, zn = C[iu], E_old_full[iu], new["expected"][iu], z_old_full[iu], z_full[iu]
    Xd = X.toarray()
    mean_size = ((Xd * n[None, :]) @ Xd.T)[iu] / np.maximum(obs, 1)
    sector = uni["ff12"].to_numpy()
    same = sector[iu[0]] == sector[iu[1]]
    popular = set(np.argsort(-k)[:50])

    def pop_share(score, top=5000):
        idx = np.argsort(-score)[:top]
        return np.mean([(a in popular) or (b in popular) for a, b in zip(iu[0][idx], iu[1][idx])]) * 100

    rows = []
    for name, e, z in (("old (popularity only)", e_old, zo), ("new (popularity + manager size)", e_new, zn)):
        top = np.argsort(-z)[:5000]
        rows.append({
            "null": name, "median observed/expected": round(float(np.median(obs[e > 0] / e[e > 0])), 2),
            "share of pairs with z>3 (%)": round(float((z > 3).mean() * 100), 1),
            "share of pairs with z<-3 (%)": round(float((z < -3).mean() * 100), 1),
            "median z": round(float(np.median(z)), 2),
            "spearman z vs popularity": round(float(pd.Series(z).corr(pd.Series(k[iu[0]] * k[iu[1]]), method="spearman")), 3),
            "spearman z vs mean size of shared managers": round(float(pd.Series(z).corr(pd.Series(mean_size), method="spearman")), 3),
            "top-5000 pairs touching a top-50-held stock (%)": round(pop_share(z), 1),
            "top-5000 pairs in the same FF12 sector (%)": round(float(same[top].mean() * 100), 1)})
    res = pd.DataFrame(rows).set_index("null").T
    res.to_csv(RESULTS / "null_test.csv")
    pd.set_option("display.width", 200, "display.max_colwidth", 60)
    print(res.to_string())
    print(f"baseline: share of all pairs in the same FF12 sector: {same.mean() * 100:.1f}%")

    rng = np.random.default_rng(42)
    pick = rng.choice(len(obs), 30000, replace=False)
    pick = pick[obs[pick] > 0]
    BLUE, INK, GRID, SOFT = "#2a78d6", "#0b0b0b", "#e6e5df", "#52514e"
    plt.rcParams.update({"axes.spines.top": False, "axes.spines.right": False, "axes.titlelocation": "left", "axes.titleweight": "bold",
                         "axes.titlesize": 11, "text.color": INK, "axes.labelcolor": SOFT, "xtick.color": SOFT, "ytick.color": SOFT, "font.size": 10})
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.0), sharey=True)
    for ax, e, title in ((axes[0], e_old, "Popularity only"), (axes[1], e_new, "Popularity and manager size")):
        ax.scatter(e[pick], obs[pick], s=4, color=BLUE, alpha=0.22, linewidths=0)
        lim = [min(e[pick][e[pick] > 0].min(), obs[pick].min()), max(e[pick].max(), obs[pick].max())]
        ax.plot(lim, lim, color=INK, lw=1, ls="--", label="Observed = expected")
        ax.set_xscale("log"); ax.set_yscale("log")
        for a in (ax.xaxis, ax.yaxis):
            a.set_major_formatter(FuncFormatter(lambda v, _: f"{v:,.0f}" if v >= 1 else f"{v:g}"))
        ax.set_xlabel("Shared holders expected by chance")
        ax.set_title(title)
        ax.grid(color=GRID, lw=0.8)
        ax.set_axisbelow(True)
    axes[0].set_ylabel("Shared holders observed")
    axes[0].legend(frameon=False, loc="upper left")
    fig.suptitle(f"Does chance explain shared holders? Pairs among the {N} largest stocks, {QUARTER}", x=0.01, ha="left", fontsize=11, fontweight="bold")
    fig.tight_layout()
    fig.savefig(FIGURES / "f7_null_calibration.png", dpi=200, bbox_inches="tight")


if __name__ == "__main__":
    main()
