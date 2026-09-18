# This file holds the shared drawing style for every figure of the paper:
# one fixed color per model family, one symbol per architecture type, and
# the picture-quality settings. Its functions:
#   apply_style — turn on the shared look (font, resolution, tight margins);
#   family_color — the color for one family name (same in every figure);
#   arch_marker — the symbol for one architecture (dense=circle, MoE=triangle,
#     unknown=diamond);
#   save_figure — write one picture as PNG (300 dpi) and PDF;
#   size_for_params — point size for a model's total parameter count.

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # draw to files, no screen needed
import matplotlib.pyplot as plt  # noqa: E402

# Fixed family colors (colorblind-safe, muted; human is always black).
FAMILY_COLORS: dict[str, str] = {
    "Qwen": "#0072B2",       # blue
    "Gemma": "#D55E00",      # vermillion
    "Granite": "#009E73",    # bluish green
    "OpenAI": "#CC79A7",     # reddish purple
    "NVIDIA": "#56B4E9",     # sky blue
    "Meta-Muse": "#E69F00",  # orange
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


def size_for_params(total_params_b: float | None) -> float:
    """Return the marker area for a model's total size (restrained sqrt)."""
    if total_params_b is None or total_params_b <= 0:
        return 60.0
    return 30.0 + 90.0 * (total_params_b / 36.0) ** 0.5


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
