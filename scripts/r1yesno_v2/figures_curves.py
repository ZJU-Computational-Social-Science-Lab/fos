# This file draws the paper's purchase-curve figure:
#   fig1_curves — ONE picture with TWO panels (blinded left, unblinded
#     right), showing how likely people/models are to say "yes, I would buy"
#     at each price point. The human average is one thick black line; every
#     model is one thin line colored by its family and drawn solid (dense
#     model), dashed (MoE) or dotted (unknown architecture). The legend sits
#     outside the panels on the right and lists the human first, then the
#     models grouped by family.
# Expected model count per panel is 16; a panel with fewer lines raises an
# error instead of quietly drawing an incomplete picture.

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from scripts.r1yesno_v2.figures_style import (
    HUMAN_COLOR,
    apply_style,
    arch_linestyle,
    family_color,
    save_figure,
)
from scripts.r1yesno_v2.registry import FAMILY_ORDER, MODELS

BLINDED = "demographics_blinded"
UNBLINDED = "demographics_unblinded"
CONDITIONS = (BLINDED, UNBLINDED)
PANEL_TITLES = {BLINDED: "blinded", UNBLINDED: "unblinded"}
HUMAN_LINEWIDTH = 2.4  # thick — the human reference must stand out
MODEL_LINEWIDTH = 1.0  # thin — 16 model lines share each panel
EXPECTED_MODELS_PER_PANEL = 16


def _mean_curve(cells: pd.DataFrame) -> pd.DataFrame:
    """Average one subject's cells over products: mean p at each price."""
    return cells.groupby("price", as_index=False)["p"].mean()


def _human_curve(human_cells: pd.DataFrame, condition: str) -> pd.DataFrame:
    """Return the human mean curve for one condition (p_human -> p)."""
    rows = human_cells.loc[human_cells["condition"] == condition].rename(
        columns={"p_human": "p"}
    )
    return _mean_curve(rows)


def _panel_order(model_ids: list[str]) -> list[str]:
    """Sort models by family (registry order), then active params, unknowns last."""
    family_rank = {family: i for i, family in enumerate(FAMILY_ORDER)}

    def sort_key(model_id: str) -> tuple[int, float, str]:
        info = MODELS[model_id]
        active = info["active_params_b"]
        return (
            family_rank.get(info["family"], len(FAMILY_ORDER)),
            float("inf") if active is None else float(active),
            model_id,
        )

    return sorted(model_ids, key=sort_key)


def _legend_handles(model_ids: list[str]) -> list:
    """Build legend lines: human first, then models grouped by family."""
    handles = [
        plt.Line2D(
            [], [], color=HUMAN_COLOR, linestyle="solid",
            linewidth=HUMAN_LINEWIDTH, label="Human",
        )
    ]
    for model_id in model_ids:
        info = MODELS[model_id]
        handles.append(
            plt.Line2D(
                [], [], color=family_color(info["family"]),
                linestyle=arch_linestyle(info["architecture"]),
                linewidth=MODEL_LINEWIDTH, label=info["short_name"],
            )
        )
    return handles


def _draw_panel(
    ax: plt.Axes,
    title: str,
    human_curve: pd.DataFrame,
    model_curves: list[tuple[str, pd.DataFrame]],
) -> None:
    """Draw one condition's panel: thick human line plus thin model lines."""
    ax.plot(
        human_curve["price"], human_curve["p"], color=HUMAN_COLOR,
        linewidth=HUMAN_LINEWIDTH, zorder=3,
    )
    for model_id, curve in model_curves:
        info = MODELS[model_id]
        ax.plot(
            curve["price"], curve["p"], color=family_color(info["family"]),
            linestyle=arch_linestyle(info["architecture"]),
            linewidth=MODEL_LINEWIDTH, zorder=2,
        )
    ax.set_xlim(15, 205)
    ax.set_ylim(0, 1)
    ax.set_xticks([20, 50, 100, 150, 200])
    ax.set_title(title, fontsize=10)


def fig1_curves(
    curves: dict[tuple[str, str], pd.DataFrame],
    human_cells: pd.DataFrame,
    outdir: Path,
) -> list[Path]:
    """Figure 1: purchase probability vs price, blinded and unblinded.

    `curves` maps (model_id, condition) to that leg's primary cells
    (product, price, p). Each panel shows the human mean curve (thick
    black) and every model's mean-over-products curve (thin, family
    color, architecture line style), with the legend outside on the right.
    Raises ValueError if a condition is missing any of the 16 models.
    """
    apply_style()
    fig, axes = plt.subplots(1, 2, figsize=(11.8, 4.6), sharey=True)
    ordered_ids: list[str] | None = None
    for ax, condition in zip(axes, CONDITIONS):
        model_ids = _panel_order(
            [model_id for (model_id, cond) in curves if cond == condition]
        )
        if len(model_ids) != EXPECTED_MODELS_PER_PANEL:
            raise ValueError(
                f"{condition}: expected {EXPECTED_MODELS_PER_PANEL} model curves, "
                f"found {len(model_ids)}: {model_ids}"
            )
        if ordered_ids is None:
            ordered_ids = model_ids
        model_curves = [
            (model_id, _mean_curve(curves[(model_id, condition)]))
            for model_id in model_ids
        ]
        _draw_panel(
            ax, PANEL_TITLES[condition],
            _human_curve(human_cells, condition), model_curves,
        )
    axes[0].set_ylabel("P(yes — would purchase)")
    axes[0].set_xlabel("price (% of regular)")
    axes[1].set_xlabel("price (% of regular)")
    assert ordered_ids is not None
    axes[1].legend(
        handles=_legend_handles(ordered_ids),
        loc="center left", bbox_to_anchor=(1.02, 0.5),
        fontsize=6.5, frameon=False, handlelength=2.6,
    )
    fig.suptitle("Purchase probability vs price", fontsize=11)
    fig.tight_layout(rect=(0, 0, 0.99, 0.95))
    return save_figure(fig, outdir, "fig1_curves")
