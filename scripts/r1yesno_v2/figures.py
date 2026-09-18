# This file draws the first three paper figures, comparing models by their
# price-response gain G (how fast purchase intent falls with price, relative
# to humans):   fig1_active_params_vs_gain — gain against the number of
# active parameters, colored by family, one dot per model, plus a side strip
# for models whose parameter count is unknown;
#   fig2_all_models_gain_ranking — all models ranked best-to-worst by gain,
#     one lollipop chart per blinding condition;
#   fig3_bias_vs_gain — average over-purchase tendency (bias B) against gain.
# Every model keeps its family color and architecture symbol everywhere.

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from adjustText import adjust_text

from scripts.r1yesno_v2.figures_style import (
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
PANEL_TITLES = {BLINDED: "blinded", UNBLINDED: "unblinded"}
G_REFERENCE = 1.0  # model falls with price exactly as fast as humans


def _with_plot_info(table: pd.DataFrame, condition: str) -> pd.DataFrame:
    """Copy one condition's rows and attach family/architecture/params."""
    rows = table.loc[table["condition"] == condition].copy()
    rows["family"] = rows["model_id"].map(lambda m: MODELS[m]["family"])
    rows["architecture"] = rows["model_id"].map(lambda m: MODELS[m]["architecture"])
    rows["total_params_b"] = rows["model_id"].map(lambda m: MODELS[m]["total_params_b"])
    rows["active_params_b"] = rows["model_id"].map(lambda m: MODELS[m]["active_params_b"])
    return rows


def _scatter_models(ax: plt.Axes, rows: pd.DataFrame, x_col: str) -> None:
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


def _label_points(ax: plt.Axes, rows: pd.DataFrame, x_col: str) -> None:
    """Write each model's short name next to its dot, nudged apart."""
    texts = [
        ax.text(
            row[x_col], row["G_lin"], row["display_name"],
            fontsize=6.2, zorder=4,
        )
        for _, row in rows.iterrows()
    ]
    adjust_text(texts, ax=ax, expand=(1.25, 1.5), arrowprops=dict(arrowstyle="-", lw=0.4))


def _add_reference_lines(ax: plt.Axes) -> None:
    """Draw the G=0 (flat model) and G=1 (human-like) reference lines."""
    ax.axhline(0.0, color="grey", linestyle=":", linewidth=0.8)
    ax.axhline(G_REFERENCE, color="black", linestyle="--", linewidth=0.9)


def _add_group_fit(ax: plt.Axes, rows: pd.DataFrame, architecture: str) -> None:
    """Draw a thin descriptive straight-line trend for one architecture group."""
    group = rows.loc[rows["architecture"] == architecture].dropna(subset=["active_params_b"])
    if len(group) < 4:
        return
    log_x = np.log10(group["active_params_b"].to_numpy(float))
    slope, intercept = np.polyfit(log_x, group["G_lin"].to_numpy(float), 1)
    grid = np.logspace(log_x.min(), log_x.max(), 32)
    line, = ax.plot(grid, intercept + slope * np.log10(grid), linewidth=0.9, alpha=0.4,
                    color="grey", linestyle="-", zorder=1)
    ax.annotate(
        f"{architecture} trend (descriptive, not causal)",
        xy=(grid[-1], intercept + slope * np.log10(grid[-1])),
        xytext=(-4, -8), textcoords="offset points", ha="right",
        fontsize=5.5, color="grey", alpha=0.85,
    )


def _add_family_marker_legend(fig: plt.Figure, rows: pd.DataFrame) -> None:
    """Draw one shared legend of family colors and architecture symbols."""
    families = list(dict.fromkeys(rows["family"]))
    handles = [
        plt.Line2D([], [], color=family_color(f), marker="o", linestyle="",
                   markersize=7, label=f)
        for f in families
    ]
    for arch, marker in (("dense", "o"), ("MoE", "^"), ("unknown", "D")):
        handles.append(
            plt.Line2D([], [], color="black", marker=marker, linestyle="",
                       markersize=6, markerfacecolor="white", label=f"arch: {arch}")
        )
    fig.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, 0.97),
               ncol=len(handles), fontsize=7, frameon=False)


def fig1_active_params_vs_gain(table: pd.DataFrame, outdir: Path) -> list[Path]:
    """Figure 1: gain G against active parameter count, blinded vs unblinded.

    Two main panels (one per blinding condition) plus a narrow strip holding
    models whose active parameter count is unknown.
    """
    apply_style()
    known = {
        c: _with_plot_info(table, c).dropna(subset=["active_params_b"])
        for c in (BLINDED, UNBLINDED)
    }
    unknown_ids = sorted(
        set(table.loc[table["active_params_b"].isna(), "model_id"])
        if "active_params_b" in table.columns
        else _unknown_ids(table)
    )
    fig = plt.figure(figsize=(10.5, 5.0))
    grid = fig.add_gridspec(1, 3, width_ratios=[1, 1, 0.30], wspace=0.28,
                            top=0.82, bottom=0.12)
    axes = [fig.add_subplot(grid[0, i]) for i in range(3)]
    for ax, condition in zip(axes[:2], (BLINDED, UNBLINDED)):
        rows = known[condition]
        _add_group_fit(ax, rows, "dense")
        _add_group_fit(ax, rows, "MoE")
        _scatter_models(ax, rows, "active_params_b")
        _add_reference_lines(ax)
        _label_points(ax, rows, "active_params_b")
        ax.set_xscale("log")
        ax.set_xlim(2.5, 45)
        clean_log_ticks(ax)
        ax.set_title(PANEL_TITLES[condition], fontsize=10)
        ax.set_xlabel("active parameters (B, log scale)")
    axes[0].set_ylabel("price-response gain  G")
    _draw_unknown_strip(axes[2], table, unknown_ids)
    _add_family_marker_legend(fig, known[UNBLINDED])
    fig.suptitle("Price-response gain vs active parameter scale", fontsize=11, y=1.00)
    return save_figure(fig, outdir, "fig1_active_params_vs_gain")


def _unknown_ids(table: pd.DataFrame) -> list[str]:
    """Return model ids whose active parameter count is unknown."""
    ids = [
        model_id for model_id in table["model_id"].unique()
        if MODELS[model_id]["active_params_b"] is None
    ]
    return sorted(ids)


def _draw_unknown_strip(
    ax: plt.Axes, table: pd.DataFrame, unknown_ids: list[str]
) -> None:
    """Draw models with unknown active params: unblinded filled, blinded open."""
    rows_by_cond = {
        condition: _with_plot_info(table, condition).loc[
            lambda frame: frame["model_id"].isin(unknown_ids)
        ]
        for condition in (BLINDED, UNBLINDED)
    }
    for model_id in unknown_ids:
        unblinded = rows_by_cond[UNBLINDED].loc[
            rows_by_cond[UNBLINDED]["model_id"] == model_id
        ]
        blinded = rows_by_cond[BLINDED].loc[rows_by_cond[BLINDED]["model_id"] == model_id]
        name, family, arch, total = _strip_point_facts(model_id)
        for rows, filled in ((blinded, False), (unblinded, True)):
            if not len(rows):
                continue
            g_value = float(rows["G_lin"].iloc[0])
            if filled:
                ax.scatter(0.0, g_value, s=size_for_params(total), c=family_color(family),
                           marker=arch_marker(arch), edgecolors="black", linewidths=0.4, zorder=3)
                ax.text(0.07, g_value, f"{name}\nunb G={g_value:.2f}", fontsize=6, zorder=4)
            else:
                ax.scatter(0.0, g_value, s=size_for_params(total), marker=arch_marker(arch),
                           facecolors="white", edgecolors=family_color(family),
                           linewidths=1.1, zorder=3)
    ax.set_xlim(-0.5, 1.1)
    ax.set_ylim(-0.15, 2.05)
    ax.set_xticks([0.0])
    ax.set_xticklabels(["?"])
    ax.set_title("unknown active params", fontsize=9)
    ax.tick_params(axis="y", labelleft=False)
    ax.axhline(G_REFERENCE, color="black", linestyle="--", linewidth=0.9)
    ax.text(0.98, 0.02, "filled: unblinded\nopen: blinded", transform=ax.transAxes,
            ha="right", va="bottom", fontsize=6, color="grey")


def _strip_point_facts(model_id: str) -> tuple[str, str, str, float | None]:
    """Return (short name, family, architecture, total params) for one model."""
    info = MODELS[model_id]
    return info["short_name"], info["family"], info["architecture"], info["total_params_b"]


def fig2_all_models_gain_ranking(table: pd.DataFrame, outdir: Path) -> list[Path]:
    """Figure 2: every model ranked by gain G, one lollipop panel per condition."""
    apply_style()
    fig, axes = plt.subplots(1, 2, figsize=(9.5, 6.2), sharex=True)
    for ax, condition in zip(axes, (BLINDED, UNBLINDED)):
        rows = _with_plot_info(table, condition).sort_values("G_lin", ascending=True)
        positions = np.arange(len(rows))
        for pos, (_, row) in zip(positions, rows.iterrows()):
            ax.plot([0.0, row["G_lin"]], [pos, pos], color=family_color(row["family"]),
                    linewidth=1.2, alpha=0.7, zorder=2)
            ax.scatter(row["G_lin"], pos, s=46, c=family_color(row["family"]),
                       marker=arch_marker(row["architecture"]), edgecolors="black",
                       linewidths=0.4, zorder=3)
        ax.set_yticks(positions)
        ax.set_yticklabels(rows["display_name"], fontsize=7.5)
        ax.axvline(G_REFERENCE, color="black", linestyle="--", linewidth=0.9)
        ax.axvline(0.0, color="grey", linestyle=":", linewidth=0.8)
        ax.set_title(PANEL_TITLES[condition], fontsize=10)
        ax.set_xlabel("price-response gain  G")
    axes[0].set_ylabel("model (sorted by G in this panel)")
    fig.suptitle("All models ranked by price-response gain", fontsize=11)
    fig.tight_layout(rect=(0, 0.02, 1, 0.97))
    return save_figure(fig, outdir, "fig2_all_models_gain_ranking")


def fig3_bias_vs_gain(table: pd.DataFrame, outdir: Path) -> list[Path]:
    """Figure 3: average purchase bias B (pp) against gain G, per condition."""
    apply_style()
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.8), sharey=True)
    for ax, condition in zip(axes, (BLINDED, UNBLINDED)):
        rows = _with_plot_info(table, condition)
        _scatter_models(ax, rows, "B_pp")
        ax.axvline(0.0, color="grey", linestyle=":", linewidth=0.8)
        ax.axhline(G_REFERENCE, color="black", linestyle="--", linewidth=0.9)
        _label_points(ax, rows, "B_pp")
        ax.set_title(PANEL_TITLES[condition], fontsize=10)
        ax.set_xlabel("bias  B  (percentage points; + = over-purchase)")
        ax.set_ylim(min(-0.1, float(rows["G_lin"].min()) - 0.1), None)
    axes[0].set_ylabel("price-response gain  G")
    _add_family_marker_legend(fig, _with_plot_info(table, UNBLINDED))
    fig.suptitle("Purchase bias vs price-response gain", fontsize=11)
    fig.tight_layout(rect=(0, 0.06, 1, 0.95))
    return save_figure(fig, outdir, "fig3_bias_vs_gain")
