from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

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
contrast_df["bias_undisclosed"] = contrast_df["M_undisclosed"] - contrast_df["H"]
contrast_df["bias_disclosed"] = contrast_df["M_disclosed"] - contrast_df["H"]
contrast_df["abs_undisclosed"] = np.abs(contrast_df["bias_undisclosed"])
contrast_df["abs_disclosed"] = np.abs(contrast_df["bias_disclosed"])

def weighted_mean(values, weights):
    return np.sum(values * weights) / np.sum(weights)

def summarize(df):
    w = df["w"].to_numpy()
    return {
        "bias_undisclosed": weighted_mean(df["bias_undisclosed"].to_numpy(), w),
        "bias_disclosed": weighted_mean(df["bias_disclosed"].to_numpy(), w),
        "abs_undisclosed": weighted_mean(df["abs_undisclosed"].to_numpy(), w),
        "abs_disclosed": weighted_mean(df["abs_disclosed"].to_numpy(), w),
    }

point = summarize(contrast_df)

# Cluster bootstrap by experiment
rng = np.random.default_rng(20261013)
exp_groups = {exp: g.copy() for exp, g in contrast_df.groupby("experiment")}
exp_names = list(exp_groups.keys())

B = 5000
boot = {k: [] for k in point.keys()}
for _ in range(B):
    sampled = rng.choice(exp_names, size=len(exp_names), replace=True)
    dfb = pd.concat([exp_groups[e] for e in sampled], ignore_index=True)
    stats = summarize(dfb)
    for k, v in stats.items():
        boot[k].append(v)
cis = {k: (np.percentile(v, 2.5), np.percentile(v, 97.5)) for k, v in boot.items()}

default_cycle = plt.rcParams["axes.prop_cycle"].by_key()["color"]
color_undisclosed = default_cycle[0]
color_disclosed = default_cycle[1]

fig, ax = plt.subplots(figsize=(7.4, 5.3))

y_positions = {
    "bias_undisclosed": 3.0,
    "bias_disclosed": 2.2,
    "abs_undisclosed": 0.9,
    "abs_disclosed": 0.1,
}
colors = {
    "bias_undisclosed": color_undisclosed,
    "bias_disclosed": color_disclosed,
    "abs_undisclosed": color_undisclosed,
    "abs_disclosed": color_disclosed,
}

for key in ["bias_undisclosed", "bias_disclosed", "abs_undisclosed", "abs_disclosed"]:
    x = point[key]
    lo, hi = cis[key]
    ax.errorbar(
        x, y_positions[key],
        xerr=[[x - lo], [hi - x]],
        fmt="o",
        markersize=8,
        capsize=4,
        linewidth=1.6,
        color=colors[key],
    )
    ax.annotate(
        f"{x:.1f}",
        (x, y_positions[key]),
        xytext=(0, 9),
        textcoords="offset points",
        ha="center",
        va="bottom",
        fontsize=9,
        color=colors[key],
    )

ax.axvline(0, linestyle="--", linewidth=1.1, alpha=0.65, color="0.35")
ax.text(0, 1.01, "Perfect agreement",
        transform=ax.get_xaxis_transform(),
        ha="center", va="bottom", fontsize=9)

ax.set_yticks([3.0, 2.2, 0.9, 0.1],
              ["Undisclosed", "Disclosed", "Undisclosed", "Disclosed"])
ax.text(-0.12, 0.80, "Signed bias", transform=ax.transAxes,
        ha="right", va="center", fontsize=10.5)
ax.text(-0.12, 0.23, "Absolute error", transform=ax.transAxes,
        ha="right", va="center", fontsize=10.5)

ax.set_xlabel("Percentage points")
ax.set_xlim(-22, 27)
ax.set_ylim(-0.45, 3.45)
ax.hlines(1.55, xmin=-22, xmax=27, linewidth=0.8, alpha=0.20, color="0.3")

fig.tight_layout()
fig.savefig(FIGDIR / "Figure3_final.png", dpi=240, bbox_inches="tight")
fig.savefig(FIGDIR / "Figure3_final.pdf", bbox_inches="tight")
