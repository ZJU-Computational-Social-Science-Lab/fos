from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

HERE = Path(__file__).resolve().parent
DATA = HERE.parent / 'data'
FIGDIR = HERE.parent
FIGDIR.mkdir(parents=True, exist_ok=True)

signed = pd.read_csv(DATA / "blinding_signed_contrasts.csv")

contrast_df = (
    signed.groupby(["experiment", "contrast", "paradigm_family"], as_index=False)
    .agg(
        H=("H", "mean"),
        M_undisclosed=("M_B", "mean"),
        M_disclosed=("M_U", "mean"),
    )
)

n_contrasts = contrast_df.groupby("experiment")["contrast"].transform("count")
contrast_df["w"] = 1.0 / n_contrasts

def recovery_slope(df, ycol):
    x = df["H"].to_numpy()
    y = df[ycol].to_numpy()
    w = df["w"].to_numpy()
    return np.sum(w * x * y) / np.sum(w * x * x)

beta_undisclosed = recovery_slope(contrast_df, "M_undisclosed")
beta_disclosed = recovery_slope(contrast_df, "M_disclosed")

default_cycle = plt.rcParams["axes.prop_cycle"].by_key()["color"]
color_undisclosed = default_cycle[0]
color_disclosed = default_cycle[1]

fig, ax = plt.subplots(figsize=(7.0, 5.9))

for row in contrast_df.itertuples():
    ax.plot([row.H, row.H], [row.M_undisclosed, row.M_disclosed],
            linewidth=0.7, alpha=0.12, color="0.5", zorder=1)

ax.scatter(contrast_df["H"], contrast_df["M_undisclosed"], s=42, alpha=0.82,
           color=color_undisclosed, marker="o", zorder=3)
ax.scatter(contrast_df["H"], contrast_df["M_disclosed"], s=48, alpha=0.82,
           color=color_disclosed, marker="s", zorder=3)

xs = np.linspace(0, 64, 200)
ax.plot(xs, xs, linestyle="--", linewidth=1.2, alpha=0.7, color="0.35", zorder=2)
ax.plot(xs, beta_undisclosed * xs, linewidth=2.0, color=color_undisclosed, zorder=2)
ax.plot(xs, beta_disclosed * xs, linewidth=2.0, color=color_disclosed, zorder=2)

ax.axhline(0, linewidth=0.7, alpha=0.20, color="0.3")
ax.set_xlim(0, 64)
ax.set_ylim(-10, 68)
ax.set_xlabel("Human treatment effect\n(difference between the two experimental conditions, percentage points)")
ax.set_ylabel("Average LLM treatment effect\n(the same difference, percentage points)")

handles = [
    Line2D([0], [0], marker="o", linestyle="None", markersize=6.5,
           markerfacecolor=color_undisclosed, markeredgecolor=color_undisclosed,
           label="Undisclosed"),
    Line2D([0], [0], marker="s", linestyle="None", markersize=6.5,
           markerfacecolor=color_disclosed, markeredgecolor=color_disclosed,
           label="Disclosed"),
    Line2D([0], [0], linestyle="--", linewidth=1.2, color="0.35",
           label="Perfect agreement"),
    Line2D([0], [0], linestyle="-", linewidth=2.0, color=color_undisclosed,
           label=f"Undisclosed fit ({beta_undisclosed:.2f})"),
    Line2D([0], [0], linestyle="-", linewidth=2.0, color=color_disclosed,
           label=f"Disclosed fit ({beta_disclosed:.2f})"),
]
ax.legend(handles=handles, frameon=False, loc="lower right", fontsize=9)

fig.tight_layout()
fig.savefig(FIGDIR / "Figure2_final.png", dpi=240, bbox_inches="tight")
fig.savefig(FIGDIR / "Figure2_final.pdf", bbox_inches="tight")
