"""
Persona generation for the Gui & Toubia (2025) unblinding study (Web
Appendix D), plus audit reports checking a batch against the paper's
coherence rules and against approximate US census marginals.

A persona is generated ONCE at the deepest tier: one joint LLM completion
fills the 11 demographic fields AND the five behavioral measures
(tightwad/spendthrift, discount rate, present bias, risk aversion, loss
aversion), plus a price blank left empty on purpose so no price assumption
sneaks into a persona. The five-tier depth axis only truncates the
RENDERING of that same dict: none/demographics/tightwad/time_preference/
risk_preference render 0/11/12/14/16 fields. This module never talks to a
network; a chat function is injected by the caller.

What each function does:
    build_persona_elicitation_prompt()  - Max-depth prompt (joint completion).
    parse_persona(raw)  - Read an answer into an 11-field persona, or None.
    generate_personas(...)  - Draw n personas via chat_fn; (personas, skipped).
    render_persona_fields(persona, depth)  - One tier's fields of a persona.
    render_demographics_block(persona)  - The demographics-tier fields.
    render_extended_block(persona)  - Demographics plus every measure.
    check_persona_diversity(personas)  - How varied a batch of personas is.
    check_persona_coherence(personas)  - How many paper rules a batch breaks.
    compare_to_census(personas, ...)  - Gap between a batch and US census.
    load_census_marginals(path)  - Read the bundled census marginals file.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Callable

from fos.experiments.sweep_kit import _SPECIAL_TOKEN, _strip_channel_wrappers
from fos.i18n import T

# The eleven demographic fields of the paper's persona profile, in the order
# the prompt template and every renderer must use them.
PERSONA_FIELDS = [
    "age",
    "gender",
    "education",
    "household_income",
    "occupation",
    "ethnicity",
    "marital_status",
    "household_size",
    "number_of_children",
    "state",
    "home_ownership",
]

# The five behavioral measures a max-depth persona carries, in the order the
# prompt template and every renderer must use them.
BEHAVIORAL_MEASURES = [
    "tightwad_spendthrift",
    "discount_rate",
    "present_bias",
    "risk_aversion",
    "loss_aversion",
]

# Fields whose value must be a whole number once "$", commas and spaces are
# removed; every other field is kept as the text the model wrote.
_INT_FIELDS = {"age", "household_income", "household_size", "number_of_children"}

# A chat function: message list and temperature in, raw model text out.
ChatFn = Callable[[list[dict[str, str]], float], str]

# Numeric edits allowed inside a whole-number field value before casting.
_NUMBER_JUNK = "$,"

# How a measure's percentile reads inside the extended block.
_SCORE_AND_PERCENTILE = "{name}: {score} (P{percentile} percentile)"

# One-line explanations of each measure's direction, used in the extended
# block. Every note names its measure and says which way the scale runs.
_MEASURE_NOTES = {
    "tightwad_spendthrift": (
        "<note: tightwad_spendthrift runs from spendthrift to tightwad; "
        "higher scores mean more tightwad, less spendthrift>"
    ),
    "discount_rate": (
        "<note: discount_rate is the yearly discount rate; higher scores "
        "mean the person is more impatient about money later>"
    ),
    "present_bias": (
        "<note: present_bias measures favoring the sooner reward; higher "
        "scores mean more present bias, less patience>"
    ),
    "risk_aversion": (
        "<note: risk_aversion runs from risk-seeking to risk-averse; higher "
        "scores mean the person is more risk-averse, less willing to gamble>"
    ),
    "loss_aversion": (
        "<note: loss_aversion measures how much more a loss hurts than an "
        "equal gain; higher scores mean more loss-averse, less willing to "
        "take symmetric bets>"
    ),
}

# How many behavioral measures each persona depth tier renders after the
# eleven demographic fields. Tiers nest strictly; "none" renders nothing.
_DEPTH_MEASURE_COUNTS = {
    "demographics": 0,
    "tightwad": 1,
    "time_preference": 3,
    "risk_preference": 5,
}

# Words that mark an occupation as retired, matched on word boundaries so
# "retired teacher" counts but "pre-retirement training" does not.
_RETIRED_WORD = re.compile(r"\bretire", re.IGNORECASE)

# Words the coherence report needs to recognise when reading a persona.
_RETIREMENT_AGE = 50
_AGE_MIN = 18
_AGE_MAX = 100

# How the census marginals file is found when no explicit path is given.
_CENSUS_DEFAULT = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "data"
    / "configs"
    / "census_marginals_us_approx.json"
)


def build_persona_elicitation_prompt(category: str, product: str) -> str:
    """Return the max-depth step-A prompt that asks for one complete persona.

    The model is told the product category and product, then handed a
    template naming every field a max-depth persona carries: the eleven
    demographic fields in PERSONA_FIELDS order, then the five behavioral
    measures in BEHAVIORAL_MEASURES order, each next to its blank
    placeholder. The template ends with the price blank written as the
    paper's literal "[a number with up to 2 decimal points]" so the model
    fills a price too, even though the price is not stored in the persona.
    Every blank is completed in ONE joint completion.
    """
    demographic_lines = [f"{field}: {_FIELD_BLANKS[field]}" for field in PERSONA_FIELDS]
    measure_lines = [
        f"{field}: {_MEASURE_BLANKS[field]}" for field in BEHAVIORAL_MEASURES
    ]
    field_lines = "\n".join([*demographic_lines, *measure_lines])
    return (
        f"Please consider the following product category: {category}.\n"
        "Suppose you are in a grocery store, and you see the following "
        f"product in that category: {product}.\n"
        "Write the profile of a person who would buy this product. Reply "
        "with the completed template below in a single message, filling "
        "every blank at once and leaving no blank empty.\n"
        f"{field_lines}\n"
        "Price this person would pay for the product: "
        "[a number with up to 2 decimal points]"
    )


# The blank placeholder text shown next to each field in the prompt template.
_FIELD_BLANKS = {
    "age": "[a whole number]",
    "gender": "[male/female/other]",
    "education": "[highest level of schooling completed]",
    "household_income": "[a whole dollar amount]",
    "occupation": "[job title]",
    "ethnicity": "[group]",
    "marital_status": "[single/married/other]",
    "household_size": "[a whole number]",
    "number_of_children": "[a whole number]",
    "state": "[two-letter US code]",
    "home_ownership": "[own/rent]",
}

# The blank placeholder text shown next to each behavioral measure in the
# max-depth prompt template, keyed by BEHAVIORAL_MEASURES name. Every blank
# asks for the score plus its percentile, the two values the renderers
# report, so a filled-in template already reads like a rendered block.
_MEASURE_BLANKS = {
    "tightwad_spendthrift": "[score and percentile, e.g. 40 (P40 percentile)]",
    "discount_rate": "[yearly rate and percentile, e.g. 6.5 (P60 percentile)]",
    "present_bias": "[score and percentile, e.g. 40 (P40 percentile)]",
    "risk_aversion": "[score and percentile, e.g. 40 (P40 percentile)]",
    "loss_aversion": "[score and percentile, e.g. 40 (P40 percentile)]",
}


def parse_persona(raw: str) -> dict[str, Any] | None:
    """Read a model answer into an eleven-field persona dict, or None.

    The answer may carry a reasoning-channel wrapper or chat-template tokens
    (both stripped first) and any number of prose lines before or after the
    answer; only "field: value" lines for PERSONA_FIELDS count, and repeated
    lines for one field are ignored. Whole-number fields are cast to
    int after "$" and "," are removed. A reply that leaves any field missing,
    empty, or not a whole number where one is expected is not a persona and
    returns None.
    """
    if not isinstance(raw, str):
        return None
    cleaned = _SPECIAL_TOKEN.sub("", _strip_channel_wrappers(raw))
    parsed: dict[str, Any] = {}
    for line in cleaned.splitlines():
        name, separator, value = line.partition(":")
        if not separator:
            continue
        name = name.strip().lower()
        if name not in PERSONA_FIELDS or name in parsed:
            continue
        value = value.strip()
        if not value or "[" in value:
            continue
        if name in _INT_FIELDS:
            digits = value.translate(str.maketrans("", "", _NUMBER_JUNK)).strip()
            if not digits:
                continue
            try:
                parsed[name] = int(digits)
            except ValueError:
                continue
        else:
            parsed[name] = value
    if len(parsed) != len(PERSONA_FIELDS):
        return None
    return {field: parsed[field] for field in PERSONA_FIELDS}


def generate_personas(
    category: str,
    product: str,
    n: int,
    chat_fn: ChatFn,
    temperature: float = 1.0,
    seed: int | None = None,
) -> tuple[list[dict[str, Any]], int]:
    """Draw n personas through chat_fn; return (personas, skipped).

    One chat call per persona: the step-A prompt goes in the user message and
    the model's raw answer is parsed. Answers that do not parse to a full
    persona are counted in skipped, never in personas. The temperature is
    forwarded to every call; seed is accepted for a uniform call signature
    (chat_fn is the source of randomness, so the same injected function and
    seed reproduce the same batch).
    """
    del seed  # chat_fn is the only source of randomness.
    personas: list[dict[str, Any]] = []
    skipped = 0
    user_prompt = build_persona_elicitation_prompt(category, product)
    system_prompt = (
        "You are generating customer profiles for a market study. Reply with "
        "only the completed field lines, one per line."
    )
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    for _ in range(n):
        raw = chat_fn(messages, temperature)
        persona = parse_persona(raw)
        if persona is None:
            skipped += 1
        else:
            personas.append(persona)
    return personas, skipped


def render_persona_fields(persona: dict[str, Any], depth: str) -> str:
    """Render the fields one persona depth tier shows, "field: value" lines.

    Depth-truncating renderer of the five-tier design: the SAME fully
    populated persona dict at a shallower tier shows a strict subset of the
    fields a deeper tier shows. "none" renders nothing; every other tier
    renders the canonical demographic fields the persona carries (in
    PERSONA_FIELDS order, plus extra scalar keys such as city) then that
    tier's behavioral measures (in BEHAVIORAL_MEASURES order up to the tier's
    cutoff), each as a "name: score (P<pct> percentile)" line with a
    "<note: ...>" line underneath. Missing keys are skipped, never KeyError
    (the TASK-1456 tolerance); an unknown depth raises ValueError.
    """
    if depth == "none":
        return ""
    if depth not in _DEPTH_MEASURE_COUNTS:
        raise ValueError(
            T(
                "error.personas.unsupported_depth",
                depth=repr(depth),
                supported=", ".join(["none", *_DEPTH_MEASURE_COUNTS]),
            )
        )
    lines = [
        f"{field}: {persona[field]}" for field in PERSONA_FIELDS if field in persona
    ]
    lines.extend(
        f"{field}: {value}"
        for field, value in persona.items()
        if field not in PERSONA_FIELDS and not isinstance(value, dict)
    )
    for name in BEHAVIORAL_MEASURES[: _DEPTH_MEASURE_COUNTS[depth]]:
        measure = persona.get(name)
        if not isinstance(measure, dict):
            continue
        score = measure.get("score")
        percentile = measure.get("percentile")
        if score is None or percentile is None:
            continue
        lines.append(
            _SCORE_AND_PERCENTILE.format(name=name, score=score, percentile=percentile)
        )
        lines.append(_MEASURE_NOTES[name])
    return "\n".join(lines)


def render_demographics_block(persona: dict[str, Any]) -> str:
    """Return one "field: value" line per field the demographics tier shows.

    A thin wrapper over render_persona_fields at the "demographics" tier, so
    callers that name that tier directly (partial personas included) keep the
    exact same rendering. A persona with none of the canonical fields
    renders an empty string, as before.
    """
    if not any(field in persona for field in PERSONA_FIELDS):
        return ""
    return render_persona_fields(persona, "demographics")


def render_extended_block(persona: dict[str, Any]) -> str:
    """Render one persona at max depth: demographics plus every measure.

    A thin wrapper over render_persona_fields at the "risk_preference" tier.
    Measures the persona lacks are skipped silently, so a persona with no
    measures renders exactly its demographics block.
    """
    return render_persona_fields(persona, "risk_preference")


def _canonical_key(persona: dict[str, Any]) -> tuple[tuple[str, Any], ...]:
    """Turn a persona dict into a hashable key for counting duplicates."""
    return tuple(sorted(persona.items()))


def check_persona_diversity(personas: list[dict[str, Any]]) -> dict[str, Any]:
    """Report how varied a batch of personas is, as five statistics.

    unique is the number of distinct profiles, top_repeat_count is how often
    the most common profile appears, top_repeat_share is that count over n,
    and distinct_ratio is (unique - 1) / (n - 1) — the share of persona pairs
    that differ. An empty batch reports zeros.
    """
    n = len(personas)
    counts = Counter(_canonical_key(persona) for persona in personas)
    unique = len(counts)
    top_repeat_count = max(counts.values(), default=0)
    if n > 1:
        distinct_ratio = (unique - 1) / (n - 1)
    else:
        distinct_ratio = 0.0
    return {
        "n": n,
        "unique": unique,
        "top_repeat_count": top_repeat_count,
        "top_repeat_share": top_repeat_count / n if n else 0.0,
        "distinct_ratio": distinct_ratio,
    }


def _rule_violations(persona: dict[str, Any]) -> list[str]:
    """List every paper coherence rule one persona breaks, by rule name."""
    broken: list[str] = []
    age = persona.get("age")
    if not isinstance(age, int) or age < _AGE_MIN or age > _AGE_MAX:
        broken.append("age_range")
    household_size = persona.get("household_size")
    children = persona.get("number_of_children")
    if (
        isinstance(household_size, int)
        and isinstance(children, int)
        and children >= household_size
    ):
        broken.append("children_capacity")
    income = persona.get("household_income")
    if isinstance(income, int) and income < 0:
        broken.append("income_nonnegative")
    occupation = persona.get("occupation")
    if (
        isinstance(occupation, str)
        and _RETIRED_WORD.search(occupation) is not None
        and isinstance(age, int)
        and age < _RETIREMENT_AGE
    ):
        broken.append("retirement_age")
    if isinstance(household_size, int) and household_size < 1:
        broken.append("household_size_min")
    return broken


def check_persona_coherence(personas: list[dict[str, Any]]) -> dict[str, Any]:
    """Report how many personas break the paper's five coherence rules.

    The report carries n_violations (each broken rule counts once, so one
    persona breaking two rules counts twice), a rates dict with one 0..1
    share per rule name, and examples listing each offending persona dict
    exactly once.
    """
    rule_names = [
        "age_range",
        "children_capacity",
        "income_nonnegative",
        "retirement_age",
        "household_size_min",
    ]
    n = len(personas)
    fires = {name: 0 for name in rule_names}
    total = 0
    examples: list[dict[str, Any]] = []
    for persona in personas:
        broken = _rule_violations(persona)
        if broken:
            total += len(broken)
            examples.append(persona)
            for name in broken:
                fires[name] += 1
    rates = {name: fires[name] / n if n else 0.0 for name in rule_names}
    return {"n_violations": total, "rates": rates, "examples": examples}


def _numeric_gap(personas: list[dict[str, Any]], field: str) -> float:
    """Mean of one numeric field across a batch, or 0.0 when batch is empty."""
    if not personas:
        return 0.0
    return sum(persona[field] for persona in personas) / len(personas)


def _share_dict(
    personas: list[dict[str, Any]], field: str, categories: list[str]
) -> dict[str, float]:
    """Share of each category value for one categorical field.

    Categories listed in the census marginals that nobody chose get share 0;
    values the batch chose that the census does not list still appear, so the
    sample report never silently drops people.
    """
    if not personas:
        return {category: 0.0 for category in categories}
    counts = Counter(persona[field] for persona in personas)
    names = list(dict.fromkeys([*categories, *counts]))
    return {name: counts.get(name, 0) / len(personas) for name in names}


def compare_to_census(
    personas: list[dict[str, Any]], marginals: dict[str, dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    """Compare a persona batch with census marginals, for gap reporting.

    Numeric marginals ("mean") compare the sample mean minus the census mean;
    categorical marginals ("shares") compare via total-variation distance,
    0.5 times the summed absolute share differences. Only the fields named in
    marginals appear in the report, each carrying the sample value, the
    census value, and the gap.
    """
    report: dict[str, dict[str, Any]] = {}
    for field, marginal in marginals.items():
        if "mean" in marginal:
            sample = _numeric_gap(personas, field)
            census = float(marginal["mean"])
            report[field] = {
                "sample": sample,
                "census": census,
                "gap": sample - census,
            }
        else:
            shares = marginal.get("shares")
            if not isinstance(shares, dict) or not shares:
                continue
            sample = _share_dict(personas, field, list(shares))
            census = {str(category): float(share) for category, share in shares.items()}
            distance = 0.5 * sum(
                abs(sample.get(category, 0.0) - census[category]) for category in census
            )
            report[field] = {
                "sample": {category: sample.get(category, 0.0) for category in census},
                "census": census,
                "gap": distance,
            }
    return report


def load_census_marginals(path: str | Path | None = None) -> dict[str, Any]:
    """Read the census marginals JSON from a path (bundled file by default).

    The bundled file holds APPROXIMATE US population marginals for gap
    reporting only — never for statistical inference. An explicit path is
    read as-is.
    """
    target = Path(path) if path is not None else _CENSUS_DEFAULT
    return json.loads(target.read_text(encoding="utf-8"))
