"""Exploratory comparison report for the new-games pilot (offline).

What this file does, in plain language:

- ``load_records`` reads every decision record from the run folder.
- ``traveler_means`` computes the mean claim per condition (with the
  shifted-range claims mapped back by subtracting 100) per model.
- ``social_shares`` computes the share choosing the generous option
  per condition per model, to compare with the published shares.
- ``allais_shares`` computes the share choosing the risky option for
  each Allais condition per model, including the certainty-removal
  effect and the x10 prize scaling.
- ``persona_gaps`` compares persona vs no-persona per condition.
- ``write_report`` assembles everything into one EXPLORATORY markdown
  report, explicitly labelled as underpowered and directional-only.
"""

from __future__ import annotations

import argparse
import json
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any

DEFAULT_DATA_DIR = Path.home() / "experiment-data/fos/sixgame/new_games_pilot"
REPORT_PATH = DEFAULT_DATA_DIR / "reports/EXPLORATORY_new_games.md"
HUMAN_TD = {"td_low": 195, "td_high": 81, "td_shift180_300": None}
PUBLISHED_SOCIAL = {
    "social_generous_prior": 0.31,
    "social_selfish_prior": 0.06,
    "social_plus1000": 0.33,
}
MODEL_LABELS = {
    "deepseek-v4-flash": "DeepSeek",
    "anthropic/claude-sonnet-5": "Claude",
    "openai/gpt-5.6-luna": "GPT",
}
TD_ORDER = ["td_low", "td_high", "td_shift180_300"]
SOCIAL_ORDER = ["social_generous_prior", "social_selfish_prior", "social_plus1000"]
ALLAIS_ORDER = [
    "allais_base_1",
    "allais_base_2",
    "allais_x10_1",
    "allais_x10_2",
]


def load_records(data_dir: Path) -> list[dict[str, Any]]:
    """Read every decision record from the run folder's JSONL files."""
    records: list[dict[str, Any]] = []
    for path in sorted(data_dir.glob("decisions_*.jsonl")):
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
    return records


def mapped_claim(record: dict[str, Any]) -> int:
    """The claim on the shared 80-200 scale (shifted claims minus 100)."""
    claim = int(record["choice"])
    return claim - 100 if record["variant"] == "td_shift180_300" else claim


def traveler_means(records: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    """Mean mapped claim per variant per model."""
    buckets: dict[str, dict[str, list[int]]] = defaultdict(lambda: defaultdict(list))
    for r in records:
        if r["game"] == "traveler":
            buckets[r["variant"]][r["model"]].append(mapped_claim(r))
    return {
        variant: {
            model: statistics.mean(claims)
            for model, claims in models.items()
        }
        for variant, models in buckets.items()
    }


def choice_share(
    records: list[dict[str, Any]], game: str, choice: str
) -> dict[str, dict[str, float]]:
    """Share of records choosing `choice`, per variant per model."""
    hits: dict[str, dict[str, list[int]]] = defaultdict(lambda: defaultdict(list))
    for r in records:
        if r["game"] == game:
            hits[r["variant"]][r["model"]].append(1 if r["choice"] == choice else 0)
    return {
        variant: {
            model: statistics.mean(shares)
            for model, shares in models.items()
        }
        for variant, models in hits.items()
    }


def persona_gap(
    records: list[dict[str, Any]], game: str, value_of
) -> dict[str, dict[str, float]]:
    """Mean(value in persona arm) minus mean(value in no-persona arm)."""
    buckets: dict[str, dict[str, list[Any]]] = defaultdict(lambda: defaultdict(list))
    for r in records:
        if r["game"] != game:
            continue
        buckets[r["variant"]][r["arm"]].append(r)
    gaps: dict[str, dict[str, float]] = {}
    for variant, arms in buckets.items():
        models = {r["model"] for rs in arms.values() for r in rs}
        gaps[variant] = {}
        for model in models:
            persona = [value_of(r) for r in arms["persona"] if r["model"] == model]
            none = [value_of(r) for r in arms["no_persona"] if r["model"] == model]
            gaps[variant][model] = statistics.mean(persona) - statistics.mean(none)
    return gaps


def fmt(values: dict[str, float]) -> str:
    """Format one table row of model -> number."""
    return " | ".join(
        f"{MODEL_LABELS[m]}: {v:.2f}" for m, v in sorted(values.items())
    )


def build_report(records: list[dict[str, Any]]) -> str:
    """Assemble the full EXPLORATORY markdown report."""
    td = traveler_means(records)
    social = choice_share(records, "social", "A")
    allais = choice_share(records, "allais", "B")
    td_gap = persona_gap(records, "traveler", mapped_claim)
    social_gap = persona_gap(
        records, "social", lambda r: 1.0 if r["choice"] == "A" else 0.0
    )
    allais_gap = persona_gap(
        records, "allais", lambda r: 1.0 if r["choice"] == "B" else 0.0
    )
    lines = [
        "# EXPLORATORY — new-games pilot comparison (n=10/cell — UNDERPOWERED)",
        "",
        "**Status: EXPLORATORY ONLY.** Every cell holds 10 observations, so",
        "every number below is directional at best. Nothing here is",
        "confirmatory; no hypothesis test is licensed at this n.",
        "Generated offline — no model calls; raw data untouched.",
        "",
        "## 1. Traveler's Dilemma — mean claim (cents, mapped to the 80-200 scale)",
        "",
        "Humans (Capra et al. 1999, periods 8-10): claims FALL as R rises",
        "(R=5: ~195 -> R=80: ~81). Shifted-range claims are mapped back by",
        "x -> x - 100, so the shift condition reads on the same scale.",
        "",
        "| condition | mean claim per model | human direction |",
        "|---|---|---|",
    ]
    for variant in TD_ORDER:
        human = (
            "claims fall as R rises" if HUMAN_TD[variant] is None
            else f"~{HUMAN_TD[variant]}"
        )
        lines.append(f"| {variant} | {fmt(td[variant])} | {human} |")
    lines += [
        "",
        "Direction check (td_low > td_high): "
        + "; ".join(
            f"{MODEL_LABELS[m]}: {'YES' if td['td_low'][m] > td['td_high'][m] else 'NO'}"
            for m in td["td_low"]
        ),
        "",
        "### Persona vs no-persona gap (persona minus no-persona, mapped claim)",
        "",
    ]
    lines += [
        f"- {variant}: {fmt(td_gap[variant])}" for variant in TD_ORDER
    ]
    lines += [
        "",
        "## 2. Social allocation — share choosing the generous option (A)",
        "",
        "Published (Charness-Rabin 2002 Table I): generous-prior .31,",
        "selfish-prior .06, imposed (550,550) .33. The +1000 condition is",
        "our constant-offset transformation (compared with the .33",
        "imposed-cell share, directionally).",
        "",
        "| condition | generous share per model | published |",
        "|---|---|---|",
    ]
    for variant in SOCIAL_ORDER:
        lines.append(
            f"| {variant} | {fmt(social[variant])} | {PUBLISHED_SOCIAL[variant]} |"
        )
    lines += [
        "",
        "### Persona vs no-persona gap (generous share)",
        "",
    ]
    lines += [f"- {v}: {fmt(social_gap[v])}" for v in SOCIAL_ORDER]
    lines += [
        "",
        "## 3. Allais-style risk — share choosing the risky option (B)",
        "",
        "Human reference (Erev et al. 2017 / KT 1979): roughly 1/2 risky in",
        "both base problems, with the certainty-removal effect: risky share",
        "is HIGHER in pair 2 (no certain option) than pair 1.",
        "",
        "| condition | risky share per model |",
        "|---|---|",
    ]
    lines += [f"| {v} | {fmt(allais[v])} |" for v in ALLAIS_ORDER]
    lines += [
        "",
        "### Certainty-removal effect (risky share pair 2 minus pair 1)",
        "",
    ]
    for scale in ("base", "x10"):
        p1, p2 = f"allais_{scale}_1", f"allais_{scale}_2"
        lines.append(
            f"- {scale}: "
            + "; ".join(
                f"{MODEL_LABELS[m]}: {allais[p2][m] - allais[p1][m]:+.2f}"
                for m in allais[p1]
            )
        )
    lines += [
        "",
        "### Prize-scaling effect (x10 minus base, risky share)",
        "",
    ]
    for pair in ("1", "2"):
        lo, hi = f"allais_base_{pair}", f"allais_x10_{pair}"
        lines.append(
            f"- pair {pair}: "
            + "; ".join(
                f"{MODEL_LABELS[m]}: {allais[hi][m] - allais[lo][m]:+.2f}"
                for m in allais[lo]
            )
        )
    lines += [
        "",
        "### Persona vs no-persona gap (risky share)",
        "",
    ]
    lines += [f"- {v}: {fmt(allais_gap[v])}" for v in ALLAIS_ORDER]
    lines += [
        "",
        "## Caveats",
        "",
        "- n=10 per cell; every difference above is within noise.",
        "- Directions only; no significance claimed anywhere.",
        "- Benchmarks are frozen literature numbers, shown for orientation.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    """Command line: write the exploratory report into the run's reports folder."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--out", type=Path, default=REPORT_PATH)
    args = parser.parse_args()
    records = load_records(args.data_dir)
    report = build_report(records)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(report, encoding="utf-8")
    print(f"wrote {args.out} ({len(records)} records)")


if __name__ == "__main__":
    main()
