# This file holds the shared drawing style for every figure of the paper:
# one fixed color per model family, one symbol and one line style per
# architecture type, and the picture-quality settings. Its functions:
#   apply_style — turn on the shared look (font, resolution, tight margins);
#   family_color — the color for one family name (same in every figure);
#   arch_marker — the symbol for one architecture (dense=circle, MoE=triangle,
#     unknown=diamond);
#   arch_linestyle — the line style for one architecture (dense=solid,
#     MoE=dashed, unknown=dotted);
#   save_figure — write one picture as PNG (300 dpi) and PDF;
#   size_for_params — point size for a model's total parameter count;
#   add_g_footnote — write the one-line definition of the gain number G along
#     the bottom of a picture, so each figure explains itself.

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # draw to files, no screen needed
import matplotlib.pyplot as plt  # noqa: E402

# Fixed family colors (muted, mutually distinct; human is always black).
# Qwen/Gemma/Granite are pinned by the figure spec (blue/orange/green); the
# rest are chosen so no two families look alike at thin-line width.
FAMILY_COLORS: dict[str, str] = {
    "Qwen": "#0072B2",       # blue
    "Gemma": "#E69F00",      # orange
    "Granite": "#009E73",    # green
    "OpenAI": "#CC79A7",     # muted reddish purple
    "NVIDIA": "#56B4E9",     # sky blue (clearly lighter than Qwen blue)
    "Meta-Muse": "#8C564B",  # muted brown
    "GLM": "#9467BD",        # muted purple
    "Other": "#7F7F7F",      # grey
}

HUMAN_COLOR = "#000000"

# One symbol per architecture, used in every figure.
ARCH_MARKERS: dict[str, str] = {
    "dense": "o",
    "MoE": "^",
    "unknown": "D",
}

# One line style per architecture, used for curve lines.
ARCH_LINESTYLES: dict[str, str] = {
    "dense": "solid",
    "MoE": "dashed",
    "unknown": "dotted",
}

FAMILY_ZORDER = {family: i + 2 for i, family in enumerate(FAMILY_COLORS)}


def apply_style() -> None:
    """Turn on the shared look for all figures (call once per process)."""
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["DejaVu Sans", "Arial", "Helvetica"],
            "pdf.fonttype": 42,  # embed TrueType text (editable in papers)
            "figure.dpi": 300,
            "savefig.dpi": 300,
            "savefig.bbox": "tight",
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "grid.alpha": 0.25,
            "grid.linewidth": 0.4,
        }
    )


def family_color(family: str) -> str:
    """Return the fixed color for one family (unknown families get grey)."""
    return FAMILY_COLORS.get(family, FAMILY_COLORS["Other"])


def arch_marker(architecture: str) -> str:
    """Return the marker symbol for one architecture type."""
    return ARCH_MARKERS.get(architecture, ARCH_MARKERS["unknown"])


def arch_linestyle(architecture: str) -> str:
    """Return the line style for one architecture type."""
    return ARCH_LINESTYLES.get(architecture, ARCH_LINESTYLES["unknown"])


def size_for_params(total_params_b: float | None) -> float:
    """Return the marker area for a model's total size (restrained sqrt)."""
    if total_params_b is None or total_params_b <= 0:
        return 60.0
    return 30.0 + 90.0 * (total_params_b / 36.0) ** 0.5


G_FOOTNOTE = (
    "G = slope ratio vs humans; 1 = human-sized, 0 = no response;"
    " ○ dense △ MoE ◇ unknown"
)


def add_g_footnote(fig: plt.Figure, y: float = 0.008) -> None:
    """Write the one-line gain-G definition in small grey text under a figure."""
    fig.text(0.01, y, G_FOOTNOTE, fontsize=6, color="grey", ha="left", va="bottom")


def clean_log_ticks(ax: plt.Axes) -> None:
    """Replace log-axis default tick labels with plain numbers (4, 10, 30)."""
    ticks = [4, 10, 30]
    ax.set_xticks(ticks)
    ax.set_xticklabels([str(t) for t in ticks])
    ax.minorticks_off()


def save_figure(fig: plt.Figure, outdir: Path, name: str) -> list[Path]:
    """Write one figure as PNG (300 dpi) and PDF; return the written paths."""
    outdir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for suffix in (".png", ".pdf"):
        path = outdir / f"{name}{suffix}"
        fig.savefig(path)
        written.append(path)
    plt.close(fig)
    return written
