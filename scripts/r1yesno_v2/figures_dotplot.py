# This file draws the paper's gain dot plot:
#   fig2_gain_dotplot — ONE picture with TWO panels (blinded left,
#     unblinded right). Each of the 16 models is one row, top to bottom in
#     the shared figure order (the human group is not plotted — its gain G
#     is the definition of the reference, not a data point). A model's dot
#     sits at the model's price-response gain G and takes the model
#     family's fixed color; circles are dense models, triangles are
#     mixture-of-experts models. Vertical reference lines mark G=0 (grey
#     dotted, no price response) and G=1 (black dashed, human-sized
#     response), and both panels share the same x range. Row labels on the
#     left read "name (active parameters, architecture)". Nothing else is
#     written inside the panels: no labels, no trend lines, no legend.
# Every model must have a G value for both conditions; anything missing
# raises an error instead of drawing a hole.

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from scripts.r1yesno_v2.figures_style import (
    BLINDED,
    CONDITIONS,
    PANEL_TITLES,
    UNBLINDED,
    apply_style,
    arch_marker,
    family_color,
    figure_row_order,
    save_figure,
)
from scripts.r1yesno_v2.registry import MODELS

EXPECTED_MODELS = 16
G_REFERENCE = 1.0  # model falls with price exactly as fast as humans
G_ZERO = 0.0  # model shows no price response
DOT_SIZE = 55
DOT_LABEL_FONTSIZE = 8.0
LIMIT_PAD_FRACTION = 0.12  # margin added on both ends of the x range


def _compact_params(active: float) -> str:
    """Format an active parameter count compactly (3.6B, 4B, 31B)."""
    if active >= 10:
        return f"{round(active)}B"
    return f"{active:g}B"


def _params_arch_label(model_id: str) -> str:
    """Build one row label: name plus active parameters and architecture."""
    info = MODELS[model_id]
    active = info["active_params_b"]
    if active is None:
        return f"{info['short_name']} (params unk, arch unk)"
    params = _compact_params(active)
    if info["architecture"] == "MoE":
        return f"{info['short_name']} ({params} active, MoE)"
    return f"{info['short_name']} ({params}, {info['architecture']})"


def _gain_table(table: pd.DataFrame, ordered_ids: list[str]) -> pd.DataFrame:
    """Pivot G by model and condition; fail loudly on any missing value."""
    pivoted = table.pivot_table(index="model_id", columns="condition", values="G_lin")
    for model_id in ordered_ids:
        for condition in CONDITIONS:
            missing = (
                model_id not in pivoted.index
                or pd.isna(pivoted.loc[model_id, condition])
            )
            if missing:
                raise ValueError(f"missing G value for {model_id} {condition}")
    return pivoted


def _gain_limits(pivoted: pd.DataFrame) -> tuple[float, float]:
    """Return the shared x-limits: every gain, 0 and 1, with a margin."""
    gains = pd.concat([pivoted[BLINDED], pivoted[UNBLINDED]])
    low = float(min(gains.min(), G_ZERO))
    high = float(max(gains.max(), G_REFERENCE))
    pad = LIMIT_PAD_FRACTION * (high - low)
    return low - pad, high + pad


def _draw_panel(
    ax: plt.Axes,
    pivoted: pd.DataFrame,
    condition: str,
    ordered_ids: list[str],
    limits: tuple[float, float],
) -> None:
    """Draw one condition's dots plus the two reference lines."""
    for row, model_id in enumerate(ordered_ids):
        info = MODELS[model_id]
        ax.scatter(
            float(pivoted.loc[model_id, condition]),
            row,
            s=DOT_SIZE,
            c=family_color(info["family"]),
            marker=arch_marker(info["architecture"]),
            edgecolors="black",
            linewidths=0.5,
            zorder=3,
        )
    ax.axvline(G_ZERO, color="grey", linestyle=":", linewidth=0.9)
    ax.axvline(G_REFERENCE, color="black", linestyle="--", linewidth=1.0)
    ax.set_xlim(*limits)
    ax.set_ylim(len(ordered_ids) - 0.2, -0.8)  # first model at the top
    ax.set_title(PANEL_TITLES[condition], fontsize=10)
    ax.set_xlabel("Price-response gain G")


def fig2_gain_dotplot(table: pd.DataFrame, outdir: Path) -> list[Path]:
    """Figure 2: price-response gain G per model, blinded and unblinded.

    Two side-by-side panels sharing the model row order (16 rows, no human
    row). Each model is one dot at its G, colored by family, circle for
    dense and triangle for MoE models. Reference lines at G=0 (grey dotted)
    and G=1 (black dashed); both panels share one x range fitted to the
    data with a margin. Row labels on the left carry active parameters and
    architecture. Raises ValueError when a model or G value is missing.
    """
    apply_style()
    ordered_ids = figure_row_order(sorted(table["model_id"].unique()))
    if len(ordered_ids) != EXPECTED_MODELS:
        raise ValueError(
            f"expected {EXPECTED_MODELS} models, found {len(ordered_ids)}: {ordered_ids}"
        )
    pivoted = _gain_table(table, ordered_ids)
    limits = _gain_limits(pivoted)
    fig, axes = plt.subplots(1, 2, figsize=(10.6, 6.2), sharey=True)
    for ax, condition in zip(axes, CONDITIONS):
        _draw_panel(ax, pivoted, condition, ordered_ids, limits)
    axes[0].set_yticks(np.arange(len(ordered_ids)))
    axes[0].set_yticklabels(
        [_params_arch_label(model_id) for model_id in ordered_ids],
        fontsize=DOT_LABEL_FONTSIZE,
    )
    axes[1].tick_params(axis="y", labelleft=False)
    fig.tight_layout()
    return save_figure(fig, outdir, "fig2_gain_dotplot")
