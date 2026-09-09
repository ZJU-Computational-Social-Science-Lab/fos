"""Human-benchmark side of the R1 interim report (Twin-2K-500 pricing).

This module builds the benchmark p(buy) table the report scores model
conditions against: per (product, price-level) share of humans who would
buy, from the Twin-2K-500 dataset's per-person wave-4 pricing survey. It
only READS the dataset directory (never writes there) and needs no network.

Why the per-person mapping is trustworthy: each participant's persona_json
stores the pricing questions with the exact shown price and the chosen
answer in one record (the question text says the category, product and
price; the answer is 1 = yes / 2 = no). So the product-price pairing never
has to guess which product a flat column slot meant. Prices are converted
to percentage-of-regular levels with the products file's regular prices -
the same percentage grid the sweep itself uses.

Plain-language map:

    benchmark_available  - Is the dataset directory usable? Returns a
                           yes/no and, when no, the reason.
    product_from_text    - The product name out of one pricing question.
    price_from_text      - The dollar price out of one pricing question.
    level_from_price     - Turn a dollar price into a percentage level using
                           the product's regular price.
    build_human_table    - Read the whole dataset and return the p(buy)
                           table plus a provenance note.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


def benchmark_available(twin_dir: Path) -> tuple[bool, str]:
    """Say whether the Twin-2K-500 dataset is usable, and why not if not."""
    if not twin_dir.is_dir():
        return False, f"dataset directory not found: {twin_dir}"
    chunks = twin_dir / "full_persona" / "chunks"
    if not chunks.is_dir() or not list(chunks.glob("*.parquet")):
        return False, f"no persona chunks under {chunks}"
    try:
        import pandas  # noqa: F401

        import pyarrow  # noqa: F401
    except ImportError as exc:
        return False, f"pandas/pyarrow unavailable in this python: {exc}"
    return True, ""


def product_from_text(text: str) -> str | None:
    """The product name from a pricing question's text, or None."""
    marker = "following product in that category: "
    if marker not in text:
        return None
    return text.split(marker, 1)[1].split(". The product is priced at: $", 1)[0]


def price_from_text(text: str) -> float | None:
    """The shown dollar price from a pricing question's text, or None."""
    match = re.search(r"priced at: \$(\d+(?:\.\d+)?)", text)
    return float(match.group(1)) if match else None


def level_from_price(price: float, regular: float | None) -> float | None:
    """Convert a shown price into a percentage-of-regular level.

    None when the product's regular price is unknown (the price cannot be
    placed on the sweep's percentage grid without it).
    """
    if regular is None or regular <= 0:
        return None
    return round(price / regular * 100.0)


def build_human_table(
    twin_dir: Path, products: list[dict[str, Any]]
) -> tuple[dict[str, Any], str]:
    """Build p(buy) per (product, level) from the dataset's per-person data.

    Reads every persona chunk under full_persona/chunks, walks each
    participant's persona_json pricing questions, and buckets the answers
    by (product, level). Returns (table, note): table carries the per-cell
    buy counts (cells = {product: {level: {"n": ..., "buys": ...}}}), the
    participant/response counts, and the chunk files used; note is a
    one-line provenance sentence. A question whose product/price/answer
    cannot be read is counted in "skipped", never silently dropped.
    """
    import pandas as pd

    regular = {p["product"]: float(p["regular_price"]) for p in products}
    chunks = sorted(
        (twin_dir / "full_persona" / "chunks").glob("persona_chunk_*.parquet")
    )
    per_cell: dict[tuple[str, float], list[int]] = {}
    files_used: list[str] = []
    pids = 0
    responses = 0
    skipped = 0
    for chunk in chunks:
        frame = pd.read_parquet(chunk, columns=["pid", "persona_json"])
        for pid, blob in zip(frame["pid"], frame["persona_json"]):
            pids += 1
            for block in json.loads(blob):
                for question in block.get("Questions") or []:
                    qid = str(question.get("QuestionID", ""))
                    if not qid.startswith("QID9"):
                        continue
                    product = product_from_text(question.get("QuestionText", ""))
                    price = price_from_text(question.get("QuestionText", ""))
                    answer = (question.get("Answers") or {}).get("SelectedByPosition")
                    if product is None or price is None or answer not in (1, 2):
                        skipped += 1
                        continue
                    level = level_from_price(price, regular.get(product))
                    if level is None:
                        skipped += 1
                        continue
                    per_cell.setdefault((product, level), []).append(answer)
                    responses += 1
        files_used.append(str(chunk))
    cells: dict[str, dict[float, dict[str, int]]] = {}
    for (product, level), answers in sorted(per_cell.items()):
        if product not in cells:
            cells[product] = {}
        cells[product][level] = {
            "n": len(answers),
            "buys": sum(1 for answer in answers if answer == 1),
        }
    table = {
        "cells": cells,
        "pids": pids,
        "responses": responses,
        "skipped": skipped,
        "files_used": files_used,
    }
    note = (
        f"rebuilt from {len(files_used)} persona chunk(s) ({pids:,} "
        f"participants, {responses:,} responses, {skipped} unparseable "
        "skipped)"
    )
    return table, note
