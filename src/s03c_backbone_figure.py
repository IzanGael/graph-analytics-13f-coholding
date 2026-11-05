"""Step 3c: chart comparing the backbone rules tested in s03b (reads results/backbone_options.csv).

Output: figures/f8_backbone_options.png
"""
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from config import FIGURES, RESULTS

BLUE, MUTED, INK, SOFT, GRID = "#2a78d6", "#b9b7ae", "#0b0b0b", "#52514e", "#e6e5df"
CHOSEN = "top-15 per stock (z>3)"
LABELS = {"global z>3": "Keep every pair with z > 3", "global z>10": "Keep every pair with z > 10",
          "global z>20": "Keep every pair with z > 20", "global z>30": "Keep every pair with z > 30",
          "top-10 per stock (z>3)": "Each stock keeps its top 10", "top-15 per stock (z>3)": "Each stock keeps its top 15",
          "top-25 per stock (z>3)": "Each stock keeps its top 25"}

d = pd.read_csv(RESULTS / "backbone_options.csv").set_index("option")
d = d.loc[list(LABELS)]
names = [LABELS[o] for o in d.index][::-1]
colors = [BLUE if o == CHOSEN else MUTED for o in d.index][::-1]
rev = d.iloc[::-1]

plt.rcParams.update({"axes.spines.top": False, "axes.spines.right": False, "axes.spines.left": False, "axes.titlelocation": "left",
                     "axes.titleweight": "bold", "axes.titlesize": 10, "text.color": INK, "axes.labelcolor": SOFT,
                     "xtick.color": SOFT, "ytick.color": INK, "font.size": 9, "xtick.bottom": False, "ytick.left": False})
fig, axes = plt.subplots(1, 4, figsize=(13, 3.6), sharey=True)
panels = [("edges", "Links kept (log scale)", "{:,.0f}"), ("isolated stocks", "Stocks left with no link\n(out of 1,000)", "{:,.0f}"),
          ("degree vs holders (spearman)", "Links still follow popularity\n(0 = no, 1 = fully)", "{:.2f}"),
          ("NMI vs sectors", "Overlap with official sectors\n(0 = none, 1 = identical)", "{:.2f}")]
for ax, (col, title, fmt) in zip(axes, panels):
    vals = rev[col]
    ax.barh(names, vals.fillna(0), color=colors, height=0.6)
    if col == "edges":
        ax.set_xscale("log")
        ax.set_xlim(0.7, 6e5)
    else:
        ax.set_xlim(0, float(np.nanmax(vals)) * 1.28 if col != "isolated stocks" else 1250)
    for i, v in enumerate(vals):
        label = "no graph" if pd.isna(v) else fmt.format(v)
        x = 1.0 if (col == "edges" and pd.isna(v)) else (v if not pd.isna(v) else 0)
        ax.text(x * (1.25 if col == "edges" else 1.0) + (0 if col == "edges" else (ax.get_xlim()[1] * 0.02)), i, label, va="center", fontsize=8.5)
    ax.set_title(title)
    ax.set_xticks([])
    ax.grid(False)
fig.suptitle("Which links to keep? Global cut-offs fail; keeping each stock's best partners works (2026 Q2, 1,000 stocks)", x=0.01, ha="left", fontsize=11, fontweight="bold")
fig.tight_layout()
fig.savefig(FIGURES / "f8_backbone_options.png", dpi=200, bbox_inches="tight")
print("saved")
