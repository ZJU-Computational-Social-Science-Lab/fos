# This file draws the paper's overview heatmap:
#   fig1_heatmap_purchase_probability — ONE picture with TWO panels
#     (blinded left, unblinded right). Rows are the human group and the 16
#     models in the shared figure order (family blocks separated by thin
#     white lines); columns are the ten price levels from 20% to 200% of
#     the regular price. A cell's color is the share of "yes, I would buy"
#     answers at that price, averaged over the 40 products. Both panels
#     share one color scale from 0 to 1 with a single colorbar labelled
#     "P(yes — would purchase)". A price level with no data at all is drawn
#     light grey and one note line below the axes says so. No other text
#     is written inside the panels.
# Each panel must hold exactly 16 models; fewer raise an error instead of
# quietly drawing an incomplete picture.

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from scripts.r1yesno_v2.figures_style import (
    BLINDED,
    CONDITIONS,
    PANEL_TITLES,
    apply_style,
    figure_row_order,
    purchase_cmap,
    save_figure,
)
from scripts.r1yesno_v2.load import PRIMARY_PRICE_MAX, PRIMARY_PRICE_MIN
from scripts.r1yesno_v2.registry import MODELS

EXPECTED_MODELS = 16
EXPECTED_PRICE_COLUMNS = 10
X_TICK_PRICES = (20.0, 100.0, 200.0)
SEPARATOR_LINEWIDTH = 1.4
ROW_LABEL_FONTSIZE = 7.5
NO_DATA_NOTE = "grey = no data"
COLORBAR_LABEL = "P(yes — would purchase)"


def _primary_prices(human_cells: pd.DataFrame) -> list[float]:
    """Return the ten primary price levels (20% to 200%), sorted ascending.

    The human reference table defines the column grid; anything outside the
    primary range (the free 0% rows) is excluded. Raises ValueError when
    the count is not exactly ten.
    """
    primary = human_cells.loc[
        human_cells["price"].between(PRIMARY_PRICE_MIN, PRIMARY_PRICE_MAX)
    ]
    prices = sorted(float(price) for price in primary["price"].unique())
    if len(prices) != EXPECTED_PRICE_COLUMNS:
        raise ValueError(
            f"expected {EXPECTED_PRICE_COLUMNS} primary price levels, found {prices}"
        )
    return prices


def _level_means(cells: pd.DataFrame, prices: list[float]) -> np.ndarray:
    """Average one subject's cells over products: one value per price level.

    A price level the subject has no cell for becomes NaN (drawn grey).
    """
    means = cells.groupby("price")["p"].mean()
    return np.array([means.get(price, np.nan) for price in prices], dtype=float)


def _condition_matrix(
    cells_by_model_cond: dict[tuple[str, str], pd.DataFrame],
    human_cells: pd.DataFrame,
    condition: str,
    ordered_ids: list[str],
    prices: list[float],
) -> np.ndarray:
    """Stack one panel's color matrix: human row first, then the models.

    Raises ValueError when a model has no cells for this condition.
    """
    human = human_cells.loc[human_cells["condition"] == condition]
    rows = [_level_means(human.rename(columns={"p_human": "p"}), prices)]
    for model_id in ordered_ids:
        key = (model_id, condition)
        if key not in cells_by_model_cond:
            raise ValueError(f"{condition}: no cells loaded for model {model_id}")
        rows.append(_level_means(cells_by_model_cond[key], prices))
    return np.array(rows)


def _block_boundaries(ordered_ids: list[str]) -> list[float]:
    """Return the row-edge y positions where a family block ends.

    The human row is its own block, so a separator sits below it and below
    every family's last model. Family membership is conveyed by order and
    these white lines only.
    """
    boundaries = [0.5]  # below the human row (matrix row 0)
    for i in range(len(ordered_ids) - 1):
        upper_family = MODELS[ordered_ids[i]]["family"]
        lower_family = MODELS[ordered_ids[i + 1]]["family"]
        if upper_family != lower_family:
            boundaries.append(float(i + 1) + 0.5)  # model i sits in row i+1
    return boundaries


def _configure_columns(ax: plt.Axes, prices: list[float]) -> None:
    """Label a readable subset of the price columns in percent."""
    tick_positions = [prices.index(price) for price in X_TICK_PRICES]
    ax.set_xticks(tick_positions)
    ax.set_xticklabels([f"{int(price)}%" for price in X_TICK_PRICES])
    ax.set_xlabel("Price (% of regular)")
    ax.grid(False)  # cell borders come from the heatmap itself, not the grid


def _draw_panel(
    ax: plt.Axes,
    matrix: np.ndarray,
    title: str,
    prices: list[float],
    row_labels: list[str],
    show_row_labels: bool,
) -> plt.AxesImage:
    """Draw one condition's heatmap panel and return its color image."""
    image = ax.imshow(
        np.ma.masked_invalid(matrix),
        aspect="auto",
        vmin=0.0,
        vmax=1.0,
        cmap=purchase_cmap(),
    )
    ax.set_title(title, fontsize=10)
    ax.set_yticks(np.arange(matrix.shape[0]))
    if show_row_labels:
        ax.set_yticklabels(row_labels, fontsize=ROW_LABEL_FONTSIZE)
    else:
        ax.tick_params(axis="y", labelleft=False)
    _configure_columns(ax, prices)
    return image


def fig1_heatmap_purchase_probability(
    cells_by_model_cond: dict[tuple[str, str], pd.DataFrame],
    human_cells: pd.DataFrame,
    outdir: Path,
) -> list[Path]:
    """Figure 1: purchase probability heatmap, blinded and unblinded.

    Rows are the human group plus the 16 models in the shared figure order
    (family blocks with thin white separators); columns are the ten price
    levels from 20% to 200%. Cell color = purchase probability averaged
    over products; both panels share one 0-1 color scale and one colorbar.
    A fully missing price level is drawn light grey and noted below the
    axes. Raises ValueError when a panel would not hold exactly 16 models.
    """
    apply_style()
    model_ids = sorted({model_id for model_id, _ in cells_by_model_cond})
    ordered_ids = figure_row_order(model_ids)
    if len(ordered_ids) != EXPECTED_MODELS:
        raise ValueError(
            f"expected {EXPECTED_MODELS} models, found {len(ordered_ids)}: {ordered_ids}"
        )
    prices = _primary_prices(human_cells)
    row_labels = ["Human"] + [MODELS[model_id]["short_name"] for model_id in ordered_ids]
    matrices = {
        condition: _condition_matrix(
            cells_by_model_cond, human_cells, condition, ordered_ids, prices
        )
        for condition in CONDITIONS
    }
    fig, axes = plt.subplots(1, 2, figsize=(9.2, 6.8), sharey=True)
    images = []
    for ax, condition in zip(axes, CONDITIONS):
        image = _draw_panel(
            ax, matrices[condition], PANEL_TITLES[condition], prices,
            row_labels, show_row_labels=condition == BLINDED,
        )
        for y in _block_boundaries(ordered_ids):
            ax.axhline(y, color="white", linewidth=SEPARATOR_LINEWIDTH)
        images.append(image)
    colorbar = fig.colorbar(images[0], ax=list(axes), pad=0.02, fraction=0.035)
    colorbar.set_label(COLORBAR_LABEL)
    _add_no_data_note_if_needed(fig, matrices)
    return save_figure(fig, outdir, "fig1_heatmap_purchase_probability")


def _add_no_data_note_if_needed(
    fig: plt.Figure,
    matrices: dict[str, np.ndarray],
) -> None:
    """Write the grey-cell note below the axes when any cell has no data."""
    if not any(bool(np.isnan(matrix).any()) for matrix in matrices.values()):
        return
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.text(0.01, 0.006, NO_DATA_NOTE, fontsize=7, color="grey", ha="left", va="bottom")
