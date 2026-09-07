"""
Sweep and diagnostic runners for the Gui & Toubia (2025) unblinding study.

This module is the executable layer that sits on top of
fos.experiments.randomization. It builds the survey prompts from the paper,
runs them against an injected chat function (so tests never touch a network),
and writes self-describing results. It contains no network code of its own.

What each function does:
    build_blinded_system_prompt()          - The Prompt-5 system prompt: the
                                             model plays a customer and fills
                                             in one blank.
    build_unblinded_system_prompt(design)  - The Prompt-6 system prompt: the
                                             Prompt-5 task plus the design's
                                             unblinding paragraph. For a
                                             blinded design it is exactly the
                                             Prompt-5 prompt.
    build_purchase_user_prompt(...)        - The Prompt-2 purchase survey shown
                                             to the customer (buy or not buy).
    build_covariate_fillin_prompt(...)     - One Prompt 1/7/8 probe that asks
                                             the model to fill in a covariate
                                             (past price, competing price, or
                                             expiry days) at a given price.
    parse_purchase(text)                   - Reads the model's answer: True for
                                             "purchase", False for
                                             "not purchase", None for anything
                                             else.
    parse_fillin_number(text)              - Reads a "$8.26"-style answer as a
                                             float, or None for garbage.
    aggregate_demand(records, levels)      - Turns sweep records into one
                                             {level, p_buy, n} bucket per price
                                             level, sorted low to high.
    build_record(...)                      - One self-describing result row for
                                             a single chat call.
    run_sweep(...)                         - Runs the full demand sweep
                                             (products x levels x draws) under
                                             one blinding condition.
    run_diagnostic(...)                    - Runs the confounding diagnostic
                                             (products x levels x covariate
                                             kinds x draws) under one blinding
                                             condition.
    summarize_confounding(records, design) - Summarizes covariate confounding
                                             per kind, mirroring
                                             randomization.check_confounding.
    write_manifest(path, ...)              - Writes a JSON run manifest with a
                                             timestamp, never shelling out.
"""

from __future__ import annotations

import json
import random
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from fos.experiments.randomization import RandomizationDesign, check_confounding
from fos.i18n import T

# The paper fixes temperature at 1.0 and draws each response independently.
_TEMPERATURE = 1.0

# Prompt text of one number, one blank: the customer fill task stays identical
# in the blinded and unblinded conditions; only the surrounding paragraph varies.
_BLINDED_TASK = (
    "You, AI, are a customer. Your task is to fill in the blank. "
    "Return the completed information without extra text."
)

# The survey that both conditions put in the user message (paper Prompt 2).
_PURCHASE_SURVEY = (
    "Please consider the following product category: {category}.\n"
    "Suppose you are in a grocery store, and you see the following product in "
    "that category: {product}.\n"
    "The product is currently priced at ${price:.2f}. Would you or would you "
    'not purchase the product? ["purchase" or "not purchase"]\n'
    "Return example: purchase"
)

# One fill-in-the-blank probe per covariate (paper Prompts 1, 7 and 8).
_COVARIATE_PROBES = {
    "last_price": (
        "The last time you purchased this product, it was priced at $ "
        "[a number with up to 2 decimal points].\n"
        "The product is currently priced at: ${price:.2f}.\n"
        "Return example 1: 3.29"
    ),
    "competing_price": (
        "The price of a similar competing product from a different brand is "
        "[a number with up to 2 decimal points].\n"
        "The product is currently priced at: ${price:.2f}.\n"
        "Return example 1: 3.29"
    ),
    "expiry_days": (
        "Suppose you purchase this product today. It will expire [a whole "
        "number] days from now.\n"
        "The product is currently priced at: ${price:.2f}.\n"
        "Return example 1: 10"
    ),
}

# A chat function injected by the caller: sends a message list and a temperature,
# returns the model's raw text answer. Runners never open a network connection.
ChatFn = Callable[[list[dict[str, str]], float], str]

# A fill-in number is decimal digits with one optional fractional part.
_NUMBER = re.compile(r"\d+(?:\.\d+)?")


def _probe_intro(category: str, product: str) -> str:
    """Return the two shared opening lines of every covariate probe."""
    return (
        f"Please consider the following product category: {category}.\n"
        "Suppose you are in a grocery store, and you see the following "
        f"product in that category: {product}."
    )


def _seeded_rng(design: RandomizationDesign, seed: int | None) -> random.Random:
    """Build the internal generator that replays identical treatment sequences.

    The per-run seed argument wins when given; otherwise the design's own seed
    is used. With no seed anywhere the generator seeds from the system clock,
    so such runs are intentionally not reproducible.
    """
    chosen = seed if seed is not None else design.seed
    return random.Random(chosen)


def _price_for_level(regular_price: float, level: float) -> float:
    """Convert a percentage-of-regular-price level into a dollar price.

    A level of 100 means the regular price itself; a level of 200 means twice
    it. The result is rounded to cents.
    """
    return round(regular_price * level / 100.0, 2)


def _system_prompt(design: RandomizationDesign, blinding: str) -> str:
    """Pick the system prompt that matches the blinding condition."""
    if blinding == "blinded":
        return build_blinded_system_prompt()
    return build_unblinded_system_prompt(design)


def build_blinded_system_prompt() -> str:
    """Return the blinded (Prompt 5) system prompt: the customer fill task."""
    return _BLINDED_TASK


def build_unblinded_system_prompt(design: RandomizationDesign) -> str:
    """Return the unblinded (Prompt 6) system prompt for this design.

    The design's unblinding paragraph (what is randomized, over what support,
    that the subject is blind to it) is prepended to the Prompt-5 fill task.
    A blinded design renders no paragraph, so the result is exactly the blinded
    prompt and the two conditions share an identical user prompt.
    """
    paragraph = design.render_unblinding()
    if not paragraph:
        return build_blinded_system_prompt()
    return (
        f"{paragraph}\n\n"
        "The customer is given the following survey. Your task is to fill in "
        "the blank. Return the completed information without extra text."
    )


def build_purchase_user_prompt(category: str, product: str, price: float) -> str:
    """Return the Prompt-2 purchase survey for one product at one price."""
    return _PURCHASE_SURVEY.format(category=category, product=product, price=price)


def build_covariate_fillin_prompt(
    kind: str, category: str, product: str, price: float
) -> str:
    """Return the Prompt 1/7/8 probe that fills one covariate at one price.

    kind must be one of "last_price", "competing_price" or "expiry_days";
    anything else raises a ValueError so a typo never silently probes the
    wrong covariate.
    """
    if kind not in _COVARIATE_PROBES:
        raise ValueError(T("error.sweep_kit.unsupported_fillin_kind", kind=repr(kind)))
    probe = _COVARIATE_PROBES[kind].format(price=price)
    return f"{_probe_intro(category, product)}\n{probe}"


def parse_purchase(text: str) -> bool | None:
    """Read a purchase answer: True, False, or None when it is not one.

    The comparison is case-insensitive and tolerates surrounding whitespace,
    quotes and sentence punctuation. Anything richer than a bare
    "purchase"/"not purchase" (for example "I would purchase it") is not a
    parseable answer and yields None.
    """
    if not isinstance(text, str):
        return None
    cleaned = text.strip().strip(" \t\"'.,;:!?()[]{}").strip().lower()
    if cleaned == "purchase":
        return True
    if cleaned == "not purchase":
        return False
    return None


def parse_fillin_number(text: str) -> float | None:
    """Read a "$8.26"-style fill-in answer as a float.

    A leading dollar sign and surrounding whitespace are tolerated. Anything
    that is not plain decimal digits (with one optional fractional part) is
    not a number and yields None.
    """
    if not isinstance(text, str):
        return None
    cleaned = text.strip()
    if cleaned.startswith("$"):
        cleaned = cleaned[1:].strip()
    if not _NUMBER.fullmatch(cleaned):
        return None
    return float(cleaned)


def aggregate_demand(
    records: list[dict[str, Any]], levels: list[float]
) -> list[dict[str, Any]]:
    """Bucket sweep records into one demand point per treatment level.

    Each record must be the output of build_record (it carries
    "treatment_value" and "parsed_purchase"). Records whose answer did not
    parse are ignored entirely; among the parsed records n is the count and
    p_buy is the share that chose to purchase. The levels argument may arrive
    unsorted; the returned buckets are sorted by level ascending.
    """
    buckets: list[dict[str, Any]] = []
    for level in sorted(levels):
        at_level = [r for r in records if r["treatment_value"] == level]
        parsed = [r for r in at_level if r["parsed_purchase"] is not None]
        purchases = sum(1 for r in parsed if r["parsed_purchase"] is True)
        p_buy = purchases / len(parsed) if parsed else 0.0
        buckets.append({"level": level, "p_buy": p_buy, "n": len(parsed)})
    return buckets


def build_record(
    design: RandomizationDesign,
    blinding: str,
    model: str,
    product: str,
    category: str,
    treatment_value: float,
    raw: str,
    parsed: bool | None,
    elapsed_seconds: float,
    seed: int | None,
) -> dict[str, Any]:
    """Build one self-describing record for a single chat call.

    The record always carries the design (as JSON), the treatment value, the
    blinding condition, model, product and category, the model's raw answer,
    its parsed purchase decision, the wall-clock seconds the call took, the
    seed, and whether the call succeeded (that is, whether the answer parsed).
    A clean "not purchase" therefore succeeds; an unparsed answer does not.
    """
    return {
        "design": design.to_json(),
        "treatment_value": treatment_value,
        "blinding": blinding,
        "model": model,
        "product": product,
        "category": category,
        "raw_content": raw,
        "parsed_purchase": parsed,
        "elapsed_seconds": elapsed_seconds,
        "succeeded": parsed is not None,
        "seed": seed,
    }


def run_sweep(
    design: RandomizationDesign,
    products: list[dict[str, Any]],
    model: str,
    chat_fn: ChatFn,
    draws: int = 1,
    blinding: str | None = None,
    seed: int | None = None,
) -> list[dict[str, Any]]:
    """Run the demand sweep: one chat call per product, level and draw.

    products are {"category", "product", "regular_price"} dicts and chat_fn is
    an injected chat function (message list and temperature in, raw text out).
    The blinding condition defaults to the design's own blinding when not
    given. A grid design visits each level exactly draws times; a uniform
    design draws fresh values from the seeded internal generator. Each call
    becomes one build_record row whose treatment value stays inside the
    design's support.
    """
    mode = design.blinding if blinding is None else blinding
    system = _system_prompt(design, mode)
    rng = _seeded_rng(design, seed)
    levels = design.grid()
    records: list[dict[str, Any]] = []
    for product in products:
        for level in levels:
            for _ in range(draws):
                value = (
                    level
                    if design.distribution == "grid"
                    else rng.uniform(design.min_value, design.max_value)
                )
                price = _price_for_level(product["regular_price"], value)
                user = build_purchase_user_prompt(
                    product["category"], product["product"], price
                )
                messages = [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ]
                started = time.monotonic()
                raw = chat_fn(messages, _TEMPERATURE)
                elapsed = time.monotonic() - started
                records.append(
                    build_record(
                        design,
                        mode,
                        model,
                        product["product"],
                        product["category"],
                        value,
                        raw,
                        parse_purchase(raw),
                        elapsed,
                        seed,
                    )
                )
    return records


def run_diagnostic(
    design: RandomizationDesign,
    products: list[dict[str, Any]],
    kinds: list[str],
    chat_fn: ChatFn,
    draws: int = 1,
    blinding: str | None = None,
    seed: int | None = None,
) -> list[dict[str, Any]]:
    """Run the confounding diagnostic: fill covariates at randomized prices.

    For each product, level and covariate kind the model gets draws chat calls
    that ask it to fill in that one covariate given the current price. Every
    successfully parsed answer becomes a flat record {design.variable: level,
    kind: filled number} — the exact shape randomization.check_confounding
    consumes. Answers that do not parse to a number are dropped, because a
    missing value cannot be correlated with the treatment.
    """
    mode = design.blinding if blinding is None else blinding
    system = _system_prompt(design, mode)
    rng = _seeded_rng(design, seed)
    levels = design.grid()
    records: list[dict[str, Any]] = []
    for product in products:
        for level in levels:
            for kind in kinds:
                value = (
                    level
                    if design.distribution == "grid"
                    else rng.uniform(design.min_value, design.max_value)
                )
                price = _price_for_level(product["regular_price"], value)
                user = build_covariate_fillin_prompt(
                    kind, product["category"], product["product"], price
                )
                messages = [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ]
                for _ in range(draws):
                    raw = chat_fn(messages, _TEMPERATURE)
                    filled = parse_fillin_number(raw)
                    if filled is not None:
                        records.append({design.variable: value, kind: filled})
    return records


def summarize_confounding(
    records: list[dict[str, Any]], design: RandomizationDesign
) -> dict[str, dict[str, float | str]]:
    """Summarize confounding for every covariate kind present in the records.

    Each record must hold the treatment under design.variable and one or more
    covariate keys. Kinds are inferred as every record key other than the
    design variable. Each kind is correlated with the treatment through
    randomization.check_confounding, so the report carries rho, its bootstrap
    confidence interval, and the ok/mild/severe flag — never a p-value.
    """
    kinds = sorted(
        {key for record in records for key in record if key != design.variable}
    )
    summary: dict[str, dict[str, float | str]] = {}
    for kind in kinds:
        with_kind = [record for record in records if kind in record]
        summary[kind] = check_confounding(with_kind, design.variable, kind)
    return summary


def write_manifest(
    path: str | Path,
    design: RandomizationDesign,
    model: str,
    draws: int,
    blinding: str,
    products: list[dict[str, Any]],
    base_url: str,
    extra: dict[str, Any] | None = None,
) -> Path:
    """Write a JSON run manifest describing one sweep, then return its path.

    The manifest stores the design JSON, the run metadata, an ISO-8601
    written-at timestamp, and any extra keys merged at the top level. It never
    shells out (no git SHA, no network) so it works offline and in tests.
    """
    payload: dict[str, Any] = {
        "design": design.to_json(),
        "model": model,
        "draws": draws,
        "blinding": blinding,
        "products": products,
        "base_url": base_url,
        "written_at": datetime.now(timezone.utc).isoformat(),
    }
    if extra:
        payload.update(extra)
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return target
