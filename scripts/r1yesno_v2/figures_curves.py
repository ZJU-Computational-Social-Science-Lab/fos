# This file draws the last two paper figures:
#   fig4_curves_blinded / fig4_curves_unblinded — one small panel per model
#     showing its average purchase-probability curve across prices, with the
#     human curve (thick black) repeated in every panel for comparison; the
#     very first panel shows the human curve alone;
#   fig5_family_scaling — one panel of gain G against active parameter count
#     with faint lines connecting the model generations inside each family,
#     so you can see whether newer generations move up or down.
# Models keep their family color and architecture symbol everywhere.

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from adjustText import adjust_text

from scripts.r1yesno_v2.figures_style import (
    HUMAN_COLOR,
    apply_style,
    arch_marker,
    clean_log_ticks,
    family_color,
    save_figure,
    size_for_params,
)
from scripts.r1yesno_v2.registry import FAMILY_ORDER, MODELS

BLINDED = "demographics_blinded"
UNBLINDED = "demographics_unblinded"
PRIMARY_PRICES = [20.0, 40.0, 60.0, 80.0, 100.0, 120.0, 140.0, 160.0, 180.0, 200.0]
MARKER_CHAR = {"o": "●", "^": "▲", "D": "◆"}
G_REFERENCE = 1.0


def _mean_curve(cells: pd.DataFrame) -> pd.DataFrame:
    """Average one model's cells over products: mean p at each price."""
    curve = cells.loc[cells["price"].between(20.0, 200.0)]
    return curve.groupby("price", as_index=False)["p"].mean()


def _panel_order(model_ids: list[str]) -> list[str]:
    """Sort models by family, then active params ascending, unknowns last."""
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


def fig4_curves(
    curves: dict[tuple[str, str], pd.DataFrame],
    human_cells: pd.DataFrame,
    condition: str,
    outdir: Path,
) -> list[Path]:
    """Figure 4: purchase-probability curves, one small panel per model."""
    apply_style()
    human_curve = _mean_curve(
        human_cells.loc[human_cells["condition"] == condition].rename(
            columns={"p_human": "p"}
        )
    )
    model_ids = _panel_order(
        [model_id for (model_id, cond) in curves if cond == condition]
    )
    n_panels = 1 + len(model_ids)
    n_cols, n_rows = 4, int(np.ceil(n_panels / 4))
    fig, axes = plt.subplots(
        n_rows, n_cols, figsize=(3.0 * n_cols, 2.3 * n_rows), sharex=True, sharey=True
    )
    flat_axes = np.asarray(axes).reshape(-1)
    for ax in flat_axes[n_panels:]:
        ax.axis("off")
    _draw_curve_panel(flat_axes[0], human_curve, human_curve, "Human", HUMAN_COLOR, "●")
    for slot, model_id in enumerate(model_ids, start=1):
        info = MODELS[model_id]
        model_curve = _mean_curve(curves[(model_id, condition)])
        _draw_curve_panel(
            flat_axes[slot], human_curve, model_curve, info["short_name"],
            family_color(info["family"]), MARKER_CHAR[arch_marker(info["architecture"])],
        )
    fig.suptitle(
        f"Purchase probability vs price (% of regular) — {PANEL_TITLES[condition]}",
        fontsize=11,
    )
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    return save_figure(fig, outdir, f"fig4_curves_{condition.split('_')[1]}")


def _draw_curve_panel(
    ax: plt.Axes,
    human_curve: pd.DataFrame,
    model_curve: pd.DataFrame,
    title: str,
    color: str,
    marker_char: str,
) -> None:
    """Draw one small-multiples panel: human line + one model's line."""
    ax.plot(human_curve["price"], human_curve["p"], color=HUMAN_COLOR,
            linewidth=2.0, zorder=2)
    ax.plot(model_curve["price"], model_curve["p"], color=color,
            linewidth=1.1, zorder=3)
    ax.set_xlim(15, 205)
    ax.set_ylim(0, 1)
    ax.set_xticks([20, 50, 100, 150, 200])
    ax.set_title(f"{title} {marker_char}", fontsize=8)


PANEL_TITLES = {BLINDED: "blinded", UNBLINDED: "unblinded"}

# Which models are connected by faint family lines (the uncensored Qwen
# fine-tune and Qwen3.8-Max are plotted as points but not connected: the
# former is a community derivative, the latter has unknown x).
FAMILY_LINE_MEMBERS: dict[str, list[str]] = {
    "Qwen": ["qwen3-4b", "qwen3-32b", "qwen3.6-27b-dense",
             "qwen3.6-35b-a3b", "qwen3.8-27b"],
    "Gemma": ["gemma-4-26b-a4b", "gemma-4-12b-it-qat", "gemma-4-31b-it-qat"],
    "Granite": ["granite-4.1-8b", "granite-4.1-30b"],
}


def _condition_gain(table: pd.DataFrame, condition: str, model_id: str) -> float | None:
    """Return one model's gain G in one condition (None if absent)."""
    rows = table.loc[(table["model_id"] == model_id) & (table["condition"] == condition)]
    if not len(rows):
        return None
    return float(rows["G_lin"].iloc[0])


def fig5_family_scaling(table: pd.DataFrame, outdir: Path) -> list[Path]:
    """Figure 5: unblinded gain G against active params, generations linked."""
    apply_style()
    fig, ax = plt.subplots(figsize=(7.6, 5.4))
    for family, members in FAMILY_LINE_MEMBERS.items():
        points = [
            (MODELS[m]["active_params_b"], _condition_gain(table, UNBLINDED, m))
            for m in members
        ]
        points = [(x, g) for x, g in points if x is not None and g is not None]
        if len(points) >= 2:
            points.sort()
            ax.plot([x for x, _ in points], [g for _, g in points],
                    color=family_color(family), linewidth=0.8, alpha=0.35, zorder=1)
    _scatter_and_label(table, ax)
    ax.axhline(G_REFERENCE, color="black", linestyle="--", linewidth=0.9)
    ax.set_xscale("log")
    ax.set_xlim(2.5, 45)
    clean_log_ticks(ax)
    ax.set_xlabel("active parameters (B, log scale)")
    ax.set_ylabel("price-response gain  G  (unblinded)")
    ax.set_title("Gain vs active parameters across families and generations", fontsize=10)
    _note_unknown_x_models(table, ax)
    fig.tight_layout()
    return save_figure(fig, outdir, "fig5_family_scaling")


def _scatter_and_label(table: pd.DataFrame, ax: plt.Axes) -> None:
    """Draw every model's dot (family color, arch symbol) with labels and
    small grey generation tags."""
    texts: list = []
    for model_id in table.loc[table["condition"] == UNBLINDED, "model_id"]:
        info = MODELS[model_id]
        if info["active_params_b"] is None:
            continue
        gain = _condition_gain(table, UNBLINDED, model_id)
        if gain is None:
            continue
        x, y = float(info["active_params_b"]), gain
        ax.scatter(x, y, s=size_for_params(info["total_params_b"]),
                   c=family_color(info["family"]), marker=arch_marker(info["architecture"]),
                   edgecolors="black", linewidths=0.4, zorder=3)
        ax.annotate(info["generation"], xy=(x, y), xytext=(4, 4),
                    textcoords="offset points", fontsize=5.2, color="grey", zorder=2)
        texts.append(ax.text(x, y, info["short_name"], fontsize=6.2, zorder=4))
    adjust_text(texts, ax=ax, expand=(1.25, 1.5), arrowprops=dict(arrowstyle="-", lw=0.4))


def _note_unknown_x_models(table: pd.DataFrame, ax: plt.Axes) -> None:
    """List models without a known x position (e.g. Qwen3.8-Max) in a corner
    note instead of guessing their parameter count."""
    notes: list[str] = []
    for model_id in table.loc[table["condition"] == UNBLINDED, "model_id"]:
        info = MODELS[model_id]
        if info["active_params_b"] is not None:
            continue
        gain = _condition_gain(table, UNBLINDED, model_id)
        if gain is None:
            continue
        notes.append(f"{info['short_name']} (params unknown): G={gain:.2f}")
    if notes:
        ax.text(
            0.02, 0.02, "not plotted (unknown active params):\n" + "\n".join(notes),
            transform=ax.transAxes, fontsize=6.5, color="grey",
            ha="left", va="bottom",
        )
