# This file holds the shared look and the shared ordering for every figure
# of the paper: one fixed color per model family, the blinding-condition
# names both figures use, the one model row order both figures share, the
# heatmap color scale, and the picture-quality and saving settings. Its
# functions:
#   apply_style — turn on the shared look (font, resolution, tight margins);
#   family_color — the color for one family name (same in every figure);
#   arch_marker — the symbol for one architecture (dense=circle, MoE=triangle,
#     unknown=circle, the neutral default);
#   purchase_cmap — the heatmap color scale (viridis) with light grey set
#     aside for "no data" cells;
#   figure_row_order — the one model order both figures use: family blocks
#     in family order, inside a block smallest active parameters first,
#     models with unknown parameters last in their block;
#   save_figure — write one picture as PNG (300 dpi) and PDF.

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # draw to files, no screen needed
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.colors import Colormap  # noqa: E402

from scripts.r1yesno_v2.registry import FAMILY_ORDER, MODELS  # noqa: E402

# Fixed family colors (muted, mutually distinct; human is always black).
# Qwen/Gemma/Granite are pinned by the figure spec (blue/orange/green); the
# rest are chosen so no two families look alike at marker size.
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

# One symbol per architecture, used in every figure. Unknown architecture
# gets the neutral circle (no diamond anywhere).
ARCH_MARKERS: dict[str, str] = {
    "dense": "o",
    "MoE": "^",
    "unknown": "o",
}

# The two blinding conditions every figure shows side by side.
BLINDED = "demographics_blinded"
UNBLINDED = "demographics_unblinded"
CONDITIONS = (BLINDED, UNBLINDED)
PANEL_TITLES = {BLINDED: "Blinded", UNBLINDED: "Unblinded"}

NO_DATA_COLOR = "lightgrey"


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


def purchase_cmap() -> Colormap:
    """Return the heatmap color scale: viridis, light grey = no data."""
    cmap = matplotlib.colormaps["viridis"].copy()
    cmap.set_bad(NO_DATA_COLOR)
    return cmap


def figure_row_order(model_ids: list[str]) -> list[str]:
    """Return the one model order both figures share.

    Models are grouped into family blocks (registry family order), inside a
    block sorted by active parameters ascending (ties broken by model id
    for a stable order), and models whose active parameter count is unknown
    go last inside their block.
    """
    family_rank = {family: i for i, family in enumerate(FAMILY_ORDER)}

    def sort_key(model_id: str) -> tuple[int, float, float, str]:
        info = MODELS[model_id]
        active = info["active_params_b"]
        known = active is not None
        return (
            family_rank.get(info["family"], len(FAMILY_ORDER)),
            0.0 if known else 1.0,  # unknown-params models last in the block
            float(active) if known else 0.0,
            model_id,
        )

    return sorted(model_ids, key=sort_key)


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
