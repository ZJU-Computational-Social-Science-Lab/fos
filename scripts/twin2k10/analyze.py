# This file analyzes the twin2k10 study's scored answers. It reads every
# model's records.jsonl from a run directory, tallies how likely the model
# considered each answer option (both letter answers and digit answers),
# averages those per arm, computes the pinned between-arm contrasts (same
# names and signs as the shipped human benchmarks), measures how much
# unblinding changed each contrast (with a seeded bootstrap confidence
# interval), and lines the model numbers up against the human benchmark
# percentages. Everything is written as tidy CSVs plus a summary.json into
# an output folder; the run directory itself is never modified.

import csv
import json
import random
from pathlib import Path
from statistics import fmean


# The pinned contrasts: experiment -> contrast name -> (arm_x, arm_y).
# Each contrast value is stat(arm_x) - stat(arm_y), with the direction
# read off the name (X_minus_Y). Names match the human benchmarks file
# (waves.wave1_3) exactly.
CONTRASTS: dict[str, dict[str, tuple[str, str]]] = {
    "allais": {"p_opt1_form1_minus_form2": ("form1", "form2")},
    "linda": {"critical_mean_conj_minus_noconj": ("conjunction", "no_conjunction")},
    "base_rate": {"mean_70_minus_30": ("70_engineers", "30_engineers")},
    "anchoring_redwood": {"mean_high_minus_low": ("high", "low")},
    "anchoring_african": {"mean_high_minus_low": ("high", "low")},
    "outcome_bias": {"mean_success_minus_failure": ("success", "failure")},
    "myside": {"mean_german_minus_ford": ("ford", "german")},
    "prob_matching": {
        "mean_majority_share_problem1_minus_problem2": ("problem1", "problem2"),
    },
    "abs_relative": {"p_yes_jacket_minus_calculator": ("jacket", "calculator")},
    "false_consensus": {},
}

# Bootstrap settings for the unblinding confidence intervals. The seed is
# fixed so two runs on the same data give byte-identical output.
BOOTSTRAP_RESAMPLES = 1000
BOOTSTRAP_SEED = 42
CI_PERCENTILES = (2.5, 97.5)


def _expected_rating_letter(label_probs: dict[str, float]) -> float:
    """The average rating when letters score A=1, B=2, ... (by position)."""
    return sum(
        (ord(label) - ord("A") + 1) * prob for label, prob in label_probs.items()
    )


def _expected_digit(label_probs: dict[str, float]) -> float:
    """The average value when labels are digit strings like "3"."""
    return sum(int(label) * prob for label, prob in label_probs.items())


def _record_statistic(record: dict, experiment: str) -> float | None:
    """The one number this record contributes to its arm's mean.

    Each experiment scores its records differently: letter answers may be
    a simple option probability or a letter-position rating; digit answers
    are averaged digit values, the critical statement's rating (row 3) for
    linda, or the mean label-1 share across rows for prob_matching.
    Returns None when the record does not carry the needed numbers.
    """
    if experiment == "allais" or experiment == "abs_relative":
        p_raw = record.get("p_raw") or {}
        return p_raw.get("A")
    if experiment == "outcome_bias" or experiment == "myside":
        p_raw = record.get("p_raw") or {}
        if not p_raw:
            return None
        return _expected_rating_letter(p_raw)
    items = record.get("digit_items") or []
    if not items:
        return None
    if experiment == "linda":
        critical = [i for i in items if i.get("row") == 3]
        if not critical:
            return None
        return _expected_digit(critical[0]["p_raw"])
    if experiment == "prob_matching":
        shares = [i["p_raw"].get("1", 0.0) for i in items]
        return fmean(shares)
    return _expected_digit(items[0]["p_raw"])


def _arm_statistics(records: list[dict]) -> dict[tuple, list[float]]:
    """Group each record's statistic by (model, experiment, blind, arm)."""
    grouped: dict[tuple, list[float]] = {}
    for record in records:
        value = _record_statistic(record, record["experiment"])
        if value is None:
            continue
        key = (record["model"], record["experiment"], record["blind"], record["arm"])
        grouped.setdefault(key, []).append(value)
    return grouped


def load_records(run_dir: Path) -> list[dict]:
    """Read every model cell's records.jsonl under the run directory.

    A "cell" is any sub-directory holding a records.jsonl file; folders
    without one (pools, scratch) are skipped. Each line becomes one dict.
    """
    records: list[dict] = []
    for path in sorted(Path(run_dir).glob("*/*/records.jsonl")):
        with open(path, encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
    return records


def _distribution_rows(records: list[dict]) -> list[list]:
    """Rows for distributions_long.csv: one per record item x answer label.

    Choice records contribute their letter labels with an empty row
    column; digit records contribute one label set per digit item, tagged
    with that item's row number.
    """
    rows: list[list] = []
    for record in records:
        base = [
            record["model"],
            record["experiment"],
            record["arm"],
            record["blind"],
            record["persona_id"],
            record["qid"],
        ]
        for label, prob in (record.get("p_raw") or {}).items():
            rows.append(base + ["", label, prob])
        for item in record.get("digit_items") or []:
            for label, prob in item["p_raw"].items():
                rows.append(base + [item["row"], label, prob])
    return rows


def arm_distributions(records: list[dict]) -> dict[tuple, float]:
    """Each answer label's mean probability, averaged over the personas.

    Keyed (model, experiment, arm, blinding, qid, row, label).
    """
    grouped: dict[tuple, list[float]] = {}
    for record in records:
        base = (
            record["model"],
            record["experiment"],
            record["arm"],
            record["blind"],
            record["qid"],
        )
        for label, prob in (record.get("p_raw") or {}).items():
            grouped.setdefault(base + ("", label), []).append(prob)
        for item in record.get("digit_items") or []:
            for label, prob in item["p_raw"].items():
                grouped.setdefault(base + (item["row"], label), []).append(prob)
    return {key: fmean(probs) for key, probs in grouped.items()}


def contrast_values(records: list[dict]) -> dict[tuple, dict[str, float]]:
    """The pinned contrasts per (model, experiment, blinding) group.

    Each contrast is stat(arm_x) - stat(arm_y) per the pinned table. A
    contrast is skipped when either arm has no data — a missing arm is
    never read as zero.
    """
    means = {key: fmean(values) for key, values in _arm_statistics(records).items()}
    by_group: dict[tuple, dict[str, float]] = {}
    for (model, experiment, blinding, arm), mean in means.items():
        by_group.setdefault((model, experiment, blinding), {})[arm] = mean
    results: dict[tuple, dict[str, float]] = {}
    for key, by_arm in by_group.items():
        for name, (arm_x, arm_y) in CONTRASTS[key[1]].items():
            if arm_x in by_arm and arm_y in by_arm:
                results.setdefault(key, {})[name] = by_arm[arm_x] - by_arm[arm_y]
    return results


def _persona_arm_values(records: list[dict]) -> dict[tuple, dict[str, float]]:
    """Each persona's mean arm statistic, keyed (model, exp, blind, arm).

    Maps each key to {persona: mean statistic} so the bootstrap can
    resample personas within a group.
    """
    grouped: dict[tuple, dict[str, list[float]]] = {}
    for record in records:
        value = _record_statistic(record, record["experiment"])
        if value is None:
            continue
        key = (record["model"], record["experiment"], record["blind"], record["arm"])
        grouped.setdefault(key, {}).setdefault(record["persona_id"], []).append(value)
    return {
        key: {persona: fmean(values) for persona, values in by_persona.items()}
        for key, by_persona in grouped.items()
    }


def unblinding_effects(records: list[dict]) -> dict[tuple, dict[str, float]]:
    """How much unblinding moved each contrast, with a bootstrap CI.

    Keyed (model, experiment, contrast). The effect is unblinded minus
    blinded; the confidence interval comes from a seeded percentile
    bootstrap that resamples personas (constant effects give a degenerate
    interval at the point estimate).
    """
    return _collect_effects(_persona_arm_values(records))


def _collect_effects(
    persona: dict[tuple, dict[str, float]],
) -> dict[tuple, dict[str, float]]:
    """Build the unblinding effect table from per-persona arm values."""
    effects: dict[tuple, dict[str, float]] = {}
    for model, experiment, blinding, arm in sorted(persona):
        if blinding != "blinded" or arm not in _contrast_arms(experiment):
            continue
        for name, (arm_x, arm_y) in CONTRASTS[experiment].items():
            if arm != arm_x:
                continue
            pair = _contrast_pair_effects(
                persona, (model, experiment), name, arm_x, arm_y
            )
            if pair is not None:
                effects[(model, experiment, name)] = pair
    return effects


def _contrast_arms(experiment: str) -> set[str]:
    """Every arm that appears in the experiment's pinned contrasts."""
    return {arm for pair in CONTRASTS[experiment].values() for arm in pair}


def _contrast_pair_effects(
    persona: dict[tuple, dict[str, float]],
    model_experiment: tuple[str, str],
    name: str,
    arm_x: str,
    arm_y: str,
) -> dict[str, float] | None:
    """One contrast's blinded/unblinded means, effect and bootstrap CI.

    Uses only personas present in all four (blinding, arm) groups; the
    per-persona effect is (unblinded X − unblinded Y) − (blinded X −
    blinded Y), resampled with the fixed seed for the interval.
    """
    model, experiment = model_experiment
    groups = {}
    for blinding in ("blinded", "unblinded"):
        for arm in (arm_x, arm_y):
            group = persona.get((model, experiment, blinding, arm))
            if group is None:
                return None
            groups[(blinding, arm)] = group
    shared = sorted(set.intersection(*(set(group) for group in groups.values())))
    if not shared:
        return None
    bx = [groups[("blinded", arm_x)][p] for p in shared]
    by = [groups[("blinded", arm_y)][p] for p in shared]
    ux = [groups[("unblinded", arm_x)][p] for p in shared]
    uy = [groups[("unblinded", arm_y)][p] for p in shared]
    blinded_vals = [x - y for x, y in zip(bx, by)]
    unblinded_vals = [x - y for x, y in zip(ux, uy)]
    deltas = [u - b for b, u in zip(blinded_vals, unblinded_vals)]
    rng = random.Random(BOOTSTRAP_SEED)
    boots = sorted(
        fmean(deltas[rng.randrange(len(deltas))] for _ in range(len(deltas)))
        for _ in range(BOOTSTRAP_RESAMPLES)
    )
    low_i = int(len(boots) * CI_PERCENTILES[0] / 100)
    high_i = min(int(len(boots) * CI_PERCENTILES[1] / 100), len(boots) - 1)
    return {
        "blinded": fmean(blinded_vals),
        "unblinded": fmean(unblinded_vals),
        "effect": fmean(deltas),
        "ci_low": boots[low_i],
        "ci_high": boots[high_i],
    }


def _write_csv(path: Path, header: list[str], rows: list[list]) -> None:
    """Write one tidy CSV with a header row."""
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)


def _human_code(label: str) -> str:
    """Translate an answer label to the human benchmark's code.

    Answer letters map to their position ("A" -> "1"); digit labels are
    already the human codes.
    """
    if label.isalpha() and len(label) == 1:
        return str(ord(label.upper()) - ord("A") + 1)
    return label


def human_comparison_rows(records: list[dict], benchmarks: dict) -> list[list]:
    """Rows for human_comparison.csv: model label probabilities beside the
    human benchmark percentages for the same code."""
    humans = benchmarks["waves"]["wave1_3"]
    dists = arm_distributions(records)
    rows: list[list] = []
    for (model, experiment, arm, blinding, _qid, _row, label), mean_prob in sorted(
        dists.items()
    ):
        code = _human_code(label)
        arm_entry = humans.get(experiment, {}).get("arms", {}).get(arm, {})
        human_pct = (arm_entry.get("dist") or {}).get(code, {}).get("pct")
        rows.append(
            [
                model,
                experiment,
                arm,
                blinding,
                code,
                mean_prob,
                human_pct if human_pct is not None else "",
            ]
        )
    return rows


def write_analysis_outputs(run_dir_or_records, benchmarks_path, out_dir: Path) -> dict:
    """Write every analysis CSV plus summary.json into the output folder.

    Accepts either a run directory (loaded read-only) or an in-memory
    record list; the benchmarks file is read but never written. Returns
    the summary dict that was written to disk.
    """
    if isinstance(run_dir_or_records, (str, Path)):
        records = load_records(Path(run_dir_or_records))
    else:
        records = list(run_dir_or_records)
    benchmarks = json.loads(Path(benchmarks_path).read_text())
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    _write_csv(
        out_dir / "distributions_long.csv",
        [
            "model",
            "experiment",
            "arm",
            "blinding",
            "persona",
            "qid",
            "row",
            "label",
            "prob",
        ],
        _distribution_rows(records),
    )

    arm_rows = [
        [*key, mean] for key, mean in sorted(arm_distributions(records).items())
    ]
    _write_csv(
        out_dir / "arm_distributions.csv",
        ["model", "experiment", "arm", "blinding", "qid", "row", "label", "mean_prob"],
        arm_rows,
    )

    contrast_rows = [
        [*key, name, value]
        for key, by_name in sorted(contrast_values(records).items())
        for name, value in by_name.items()
    ]
    _write_csv(
        out_dir / "contrasts.csv",
        ["model", "experiment", "blinding", "contrast", "value"],
        contrast_rows,
    )

    effect_rows = [
        [
            *key,
            stats["blinded"],
            stats["unblinded"],
            stats["effect"],
            stats["ci_low"],
            stats["ci_high"],
        ]
        for key, stats in sorted(unblinding_effects(records).items())
    ]
    _write_csv(
        out_dir / "unblinding_effects.csv",
        [
            "model",
            "experiment",
            "contrast",
            "blinded",
            "unblinded",
            "effect",
            "ci_low",
            "ci_high",
        ],
        effect_rows,
    )

    _write_csv(
        out_dir / "human_comparison.csv",
        ["model", "experiment", "arm", "blinding", "code", "llm_prob", "human_pct"],
        human_comparison_rows(records, benchmarks),
    )

    summary = {
        "study": "twin2k10",
        "records": len(records),
        "contrast_rows": len(contrast_rows),
        "unblinding_rows": len(effect_rows),
    }
    with open(out_dir / "summary.json", "w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2)
        handle.write("\n")
    return summary
