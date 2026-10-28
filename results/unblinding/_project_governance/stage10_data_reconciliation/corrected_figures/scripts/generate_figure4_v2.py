from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
DATA = HERE.parent / 'data'
FIGDIR = HERE.parent
FIGDIR.mkdir(parents=True, exist_ok=True)

models = pd.read_csv(DATA / "disclosure_model_level.csv")
experiments = pd.read_csv(DATA / "disclosure_experiment_level.csv")

model_label_map = {
    "gemma-4-12b-it-qat": "Gemma 4 12B",
    "gemma-4-26b-a4b": "Gemma 4 26B-A4B",
    "gemma-4-31b-it-qat": "Gemma 4 31B",
    "glm-4.7-flash": "GLM 4.7 Flash",
    "gpt-oss-20b": "GPT-OSS-20B",
    "granite-4.1-30b": "Granite 4.1 30B",
    "granite-4.1-8b": "Granite 4.1 8B",
    "muse-glimmer": "Muse Glimmer",
    "nemotron-cascade-2-30b-a3b": "Nemotron Cascade 2 30B-A3B",
    "qwen3-32b": "Qwen3 32B",
    "qwen3-4b": "Qwen3 4B",
    "qwen3.6-27b-dense": "Qwen3.6 27B",
    "qwen3.6-35b-a3b": "Qwen3.6 35B-A3B",
    "qwen3.6-35b-a3b-uncensored": "Qwen3.6 35B-A3B UC",
    "qwen3.8-27b": "Qwen3.8 27B",
}
exp_label_map = {
    "abs_relative": "Absolute vs relative",
    "allais": "Allais",
    "anchoring_african": "Anchoring (African countries)",
    "anchoring_redwood": "Anchoring (redwood)",
    "disease": "Disease framing",
    "fire_extinguisher": "Fire extinguisher",
    "less_is_more": "Less is more",
    "linda": "Linda",
    "myside": "Myside bias",
    "outcome_bias": "Outcome bias",
    "prob_matching": "Probability matching",
    "seatbelt": "Seatbelt",
    "sunk_cost": "Sunk cost",
    "wta_wtp": "WTA / WTP",
}

models["label"] = models["model"].map(model_label_map).fillna(models["model"])
experiments["label"] = experiments["experiment"].map(exp_label_map).fillna(experiments["experiment"])

models = models.sort_values("label").reset_index(drop=True)
experiments = experiments.sort_values("label").reset_index(drop=True)

default_cycle = plt.rcParams["axes.prop_cycle"].by_key()["color"]
color_undisclosed = default_cycle[0]
color_disclosed = default_cycle[1]

xlab = "Recovery slope\n(1 = human-sized effect; below 1 = smaller than humans; above 1 = larger than humans)"

# Figure 4A
fig, ax = plt.subplots(figsize=(8.5, 6.3))
y = np.arange(len(models))
for yi, row in zip(y, models.itertuples()):
    ax.plot([row.recovery_blinded, row.recovery_unblinded], [yi, yi], linewidth=1.6, color="0.70")

ax.scatter(models["recovery_blinded"], y, s=42, marker="o", color=color_undisclosed, label="Undisclosed", zorder=3)
ax.scatter(models["recovery_unblinded"], y, s=48, marker="s", color=color_disclosed, label="Disclosed", zorder=3)

ax.axvline(1, linestyle="--", linewidth=1.2, color="0.35")
ax.text(1, 1.01, "Human-sized effect", transform=ax.get_xaxis_transform(),
        ha="center", va="bottom", fontsize=9)

ax.set_yticks(y, models["label"])
ax.invert_yaxis()
ax.set_xlabel(xlab)
ax.set_ylabel("")
ax.legend(frameon=False, loc="lower right")
ax.set_xlim(-0.35, 2.15)

fig.tight_layout()
fig.savefig(FIGDIR / "Figure4A_by_model_v2.png", dpi=240, bbox_inches="tight")
fig.savefig(FIGDIR / "Figure4A_by_model_v2.pdf", bbox_inches="tight")
plt.close(fig)

# Figure 4B
fig, ax = plt.subplots(figsize=(8.9, 6.8))
y = np.arange(len(experiments))
for yi, row in zip(y, experiments.itertuples()):
    ax.plot([row.recovery_blinded, row.recovery_unblinded], [yi, yi], linewidth=1.6, color="0.70")

ax.scatter(experiments["recovery_blinded"], y, s=42, marker="o", color=color_undisclosed, label="Undisclosed", zorder=3)
ax.scatter(experiments["recovery_unblinded"], y, s=48, marker="s", color=color_disclosed, label="Disclosed", zorder=3)

ax.axvline(1, linestyle="--", linewidth=1.2, color="0.35")
ax.text(1, 1.01, "Human-sized effect", transform=ax.get_xaxis_transform(),
        ha="center", va="bottom", fontsize=9)

ax.set_yticks(y, experiments["label"])
ax.invert_yaxis()
ax.set_xlabel(xlab)
ax.set_ylabel("")
ax.legend(frameon=False, loc="lower right")
ax.set_xlim(-4.2, 4.35)

fig.tight_layout()
fig.savefig(FIGDIR / "Figure4B_by_experiment_v2.png", dpi=240, bbox_inches="tight")
fig.savefig(FIGDIR / "Figure4B_by_experiment_v2.pdf", bbox_inches="tight")
plt.close(fig)
