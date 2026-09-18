# This file draws the paper's gain-vs-scale figure:
#   fig2_gain_vs_active_params — ONE picture with TWO main panels (blinded
#     left, unblinded right) plus a narrow third strip for the models whose
#     active parameter count is unknown (expected: Qwen3.8-Max only). Each
#     point is one model: x = active parameters (log scale), y = price-response
#     gain G. Points take their family color (same map as fig1_curves), a
#     symbol per architecture (circle dense, triangle MoE, diamond unknown)
#     and a size by total parameters. Every point is labeled with the model's
#     short name (labels nudged apart so they don't overlap). Dashed/dotted
#     reference lines mark G=1 (human-sized response) and G=0 (no response).
#     One footnote below the axes defines G and the symbols; nothing else is
#     written inside the panels, and no trend lines are fitted.

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from adjustText import adjust_text

from scripts.r1yesno_v2.figures_style import (
    add_g_footnote,
    apply_style,
    arch_marker,
    clean_log_ticks,
    family_color,
    save_figure,
    size_for_params,
)
from scripts.r1yesno_v2.registry import MODELS

BLINDED = "demographics_blinded"
UNBLINDED = "demographics_unblinded"
CONDITIONS = (BLINDED, UNBLINDED)
PANEL_TITLES = {BLINDED: "blinded", UNBLINDED: "unblinded"}
G_REFERENCE = 1.0  # model falls with price exactly as fast as humans
G_ZERO = 0.0  # model shows no price response


def _with_plot_info(table: pd.DataFrame, condition: str) -> pd.DataFrame:
    """Copy one condition's rows and attach family/architecture/params."""
    rows = table.loc[table["condition"] == condition].copy()
    rows["short_name"] = rows["model_id"].map(lambda m: MODELS[m]["short_name"])
    rows["family"] = rows["model_id"].map(lambda m: MODELS[m]["family"])
    rows["architecture"] = rows["model_id"].map(lambda m: MODELS[m]["architecture"])
    rows["total_params_b"] = rows["model_id"].map(lambda m: MODELS[m]["total_params_b"])
    rows["active_params_b"] = rows["model_id"].map(lambda m: MODELS[m]["active_params_b"])
    return rows


def _gain_axis_limits(all_gains: pd.Series) -> tuple[float, float]:
    """Return y-limits fitting every gain value, the 0 and 1 lines, and labels.

    The top adds 15% headroom above the tallest point (its name label stays
    inside the picture); the bottom sits below the 0 line and the lowest gain.
    """
    top = max(float(all_gains.max()) * 1.15, G_REFERENCE * 1.15)
    bottom = min(G_ZERO - 0.1, float(all_gains.min()) - 0.1)
    return bottom, top


def _draw_points(ax: plt.Axes, rows: pd.DataFrame, x_col: str) -> None:
    """Draw one colored, marker-shaped, size-scaled dot per model row."""
    for _, row in rows.iterrows():
        ax.scatter(
            row[x_col],
            row["G_lin"],
            s=size_for_params(row["total_params_b"]),
            c=family_color(row["family"]),
            marker=arch_marker(row["architecture"]),
            edgecolors="black",
            linewidths=0.4,
            zorder=3,
        )


def _add_reference_lines(ax: plt.Axes) -> None:
    """Draw the G=0 (flat model) and G=1 (human-like) reference lines."""
    ax.axhline(G_ZERO, color="grey", linestyle=":", linewidth=0.8)
    ax.axhline(G_REFERENCE, color="black", linestyle="--", linewidth=0.9)


def _label_points(ax: plt.Axes, rows: pd.DataFrame, x_col: str) -> None:
    """Write each model's short name next to its dot, nudged apart."""
    texts = [
        ax.text(
            row[x_col], row["G_lin"], row["short_name"],
            fontsize=6.2, zorder=4,
        )
        for _, row in rows.iterrows()
    ]
    adjust_text(texts, ax=ax, expand=(1.25, 1.5), arrowprops=dict(arrowstyle="-", lw=0.4))


def _family_legend_handles(families: list[str]) -> list:
    """Build one color-swatch handle per family (registry order)."""
    return [
        plt.Line2D([], [], color=family_color(f), marker="o", linestyle="",
                   markersize=6.5, label=f)
        for f in families
    ]


def _draw_unknown_strip(
    ax: plt.Axes,
    table: pd.DataFrame,
    unknown_ids: list[str],
    y_bottom: float,
    y_top: float,
) -> None:
    """Draw models with unknown active params: one point per blinding condition.

    The strip's x axis holds the two conditions as categories; each model
    appears once per condition (same color/symbol rules as the main panels)
    and is labeled with its short name. Raises ValueError if a condition row
    is missing for an unknown-params model.
    """
    for model_id in unknown_ids:
        rows = table.loc[table["model_id"] == model_id]
        for x, condition in enumerate(CONDITIONS):
            condition_rows = rows.loc[rows["condition"] == condition]
            if not len(condition_rows):
                raise ValueError(
                    f"unknown-params model {model_id} has no {condition} row"
                )
            info = MODELS[model_id]
            ax.scatter(
                float(x), float(condition_rows["G_lin"].iloc[0]),
                s=size_for_params(info["total_params_b"]),
                c=family_color(info["family"]),
                marker=arch_marker(info["architecture"]),
                edgecolors="black", linewidths=0.4, zorder=3,
            )
            gain = float(condition_rows["G_lin"].iloc[0])
            ax.text(
                float(x), gain, info["short_name"],
                fontsize=6.2, ha="center", va="bottom", zorder=4,
            )
    ax.set_xlim(-0.6, 1.6)
    ax.set_ylim(y_bottom, y_top)
    ax.set_xticks([0.0, 1.0])
    ax.set_xticklabels(["blinded", "unblinded"], fontsize=7)
    ax.set_title("unknown active params", fontsize=9)
    ax.tick_params(axis="y", labelleft=False)
    _add_reference_lines(ax)


def fig2_gain_vs_active_params(table: pd.DataFrame, outdir: Path) -> list[Path]:
    """Figure 2: gain G against active parameter count, blinded vs unblinded.

    Two main panels (one per blinding condition) plus a narrow strip holding
    models whose active parameter count is unknown. Family colors, G=0/G=1
    reference lines, short-name labels, one G-definition footnote, no trend
    lines and no other in-panel text.
    """
    apply_style()
    known = {
        c: _with_plot_info(table, c).dropna(subset=["active_params_b"])
        for c in CONDITIONS
    }
    unknown_ids = sorted(
        model_id for model_id in table["model_id"].unique()
        if MODELS[model_id]["active_params_b"] is None
    )
    gains = pd.concat([frame["G_lin"] for frame in known.values()])
    y_bottom, y_top = _gain_axis_limits(gains)
    fig = plt.figure(figsize=(10.5, 5.0))
    grid = fig.add_gridspec(1, 3, width_ratios=[1, 1, 0.30], wspace=0.10,
                            top=0.86, bottom=0.14)
    axes = [fig.add_subplot(grid[0, i]) for i in range(3)]
    for ax, condition in zip(axes[:2], CONDITIONS):
        rows = known[condition]
        _draw_points(ax, rows, "active_params_b")
        _add_reference_lines(ax)
        _label_points(ax, rows, "active_params_b")
        ax.set_xscale("log")
        ax.set_xlim(2.5, 45)
        ax.set_ylim(y_bottom, y_top)
        clean_log_ticks(ax)
        ax.set_title(PANEL_TITLES[condition], fontsize=10)
        ax.set_xlabel("active parameters (B, log scale)")
    axes[0].set_ylabel("price-response gain  G")
    _draw_unknown_strip(axes[2], table, unknown_ids, y_bottom, y_top)
    families = list(dict.fromkeys(
        _with_plot_info(table, UNBLINDED)["family"]
    ))
    fig.legend(
        handles=_family_legend_handles(families),
        loc="upper center", bbox_to_anchor=(0.5, 1.0),
        ncol=len(families), fontsize=7.5, frameon=False,
    )
    add_g_footnote(fig, y=0.015)
    return save_figure(fig, outdir, "fig2_gain_vs_active_params")
