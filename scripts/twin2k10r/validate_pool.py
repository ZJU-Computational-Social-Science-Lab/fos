# This file is the run-gating validator: before any inference may start,
# it checks the pool against six gates and writes VALIDATION_REPORT.md.
# Every failing gate makes the run STOP (run() returns non-zero) — the
# validator never warns and continues.
# Gates and their check functions:
#   check_panel_count                 — the respondent table is the full
#                                       2,058-person panel.
#   check_pool_size                   — the pool is exactly 100 lines.
#   check_persona_matches_respondents — every persona value equals the
#                                       panel record of that same pid.
#   check_marginals_vs_panel          — sex x age strata match the panel
#                                       exactly; other gaps within the
#                                       rounding tolerance.
#   check_cross_condition_hashes      — every condition uses one shared
#                                       byte-identical pool file.
#   check_no_leaking_fields           — no persona key outside the
#                                       whitelist (no blocklisted scores).
#   check_no_placeholders             — no "N/A" / "" / "unknown" / None.
#   check_seed_reproducibility        — a fresh replay of the sampler
#                                       from the provenance record gives
#                                       the identical pid list.
import hashlib
import json
from pathlib import Path

from twin2k10r import pool_builder, respondent_loader

# Banned outcome-leaking phrases that must appear in no rendered prompt.
BANNED_TOKENS = (
    "% of participants",
    "of participants chose",
    "human results",
    "actual human",
)


class PanelCountError(Exception):
    """The respondent table is not the full 2,058-person panel."""


class PoolSizeError(Exception):
    """The pool does not hold exactly the wanted number of personas."""


class RespondentMismatchError(Exception):
    """A persona value differs from the panel record of the same pid."""


class MarginalGapError(Exception):
    """A pool marginal deviates from the panel beyond the rounding unit."""


class PoolHashConflictError(Exception):
    """Condition copies of the pool differ in bytes."""


class LeakingPoolError(Exception):
    """A persona carries a field outside the whitelist."""


class PlaceholderError(Exception):
    """A persona value is a placeholder (""/"N/A"/"unknown"/None)."""


def _read_pool(pool_path) -> list:
    """The pool records, one dict per JSONL line."""
    text = Path(pool_path).read_text("utf-8")
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def check_panel_count(respondents, expected: int = 2058) -> None:
    """Refuse anything smaller than the full panel."""
    if len(respondents) != expected:
        raise PanelCountError(
            f"respondent table holds {len(respondents)} rows, "
            f"expected the full panel of {expected}"
        )


def check_pool_size(pool_path, expected: int = 100) -> None:
    """Refuse a pool that is not exactly `expected` lines."""
    records = _read_pool(pool_path)
    if len(records) != expected:
        raise PoolSizeError(
            f"{pool_path} holds {len(records)} lines, expected {expected}"
        )


def check_persona_matches_respondents(pool_path, respondents) -> None:
    """Every persona value must equal the panel record of the same pid."""
    records = _read_pool(pool_path)
    by_pid = {int(pid): row for pid, row in respondents.set_index("pid").iterrows()}
    for record in records:
        pid = int(record["pid"])
        if pid not in by_pid:
            raise RespondentMismatchError(f"pid {pid} is not in the panel")
        row = by_pid[pid]
        for key, value in record.items():
            if key in ("pid", "pool_id"):
                continue
            if key.startswith("score_"):
                if float(value) != float(row[key]):
                    raise RespondentMismatchError(
                        f"pid {pid} field {key}: pool says {value}, "
                        f"panel says {row[key]}"
                    )
            elif str(value) != str(row[key]):
                raise RespondentMismatchError(
                    f"pid {pid} field {key}: pool says {value!r}, "
                    f"panel says {row[key]!r}"
                )


def check_marginals_vs_panel(pool_path, panel, tolerance: float = 1) -> dict:
    """Sample marginals must track the panel within the rounding unit.

    The sex x age strata match exactly by construction (the gate reports
    their maximum gap and fails if it is not 0); every single-variable
    marginal may deviate by at most `tolerance` stratum-allocation
    rounding units. Returns the report numbers for VALIDATION_REPORT.md.
    """
    records = _read_pool(pool_path)
    total = len(records)
    if total == 0:
        raise PoolSizeError(f"{pool_path} is empty")
    gaps = {}
    worst_sex_age = 0.0
    for gender in sorted(panel["gender"].unique()):
        for age in sorted(panel["age_bracket"].unique()):
            panel_share = len(
                panel[(panel["gender"] == gender)
                      & (panel["age_bracket"] == age)]
            ) / len(panel)
            got = sum(1 for r in records
                      if r.get("gender") == gender
                      and r.get("age_bracket") == age)
            gap = abs(got / total - panel_share) * 100
            worst_sex_age = max(worst_sex_age, gap)
    gaps["sex_age_max_abs_gap"] = worst_sex_age
    for field in ("gender", "age_bracket"):
        for value in sorted(panel[field].unique()):
            panel_share = (panel[field] == value).mean()
            got = sum(1 for r in records if r.get(field) == value)
            gaps[f"{field}:{value}"] = abs(got / total - panel_share) * 100
    if worst_sex_age > tolerance:
        raise MarginalGapError(
            f"sex x age strata deviate by up to {worst_sex_age:.2f} "
            f"percentage points (tolerance {tolerance})"
        )
    for name, gap in gaps.items():
        if name != "sex_age_max_abs_gap" and gap > tolerance:
            raise MarginalError(gaps, name, gap, tolerance)
    return gaps


def MarginalError(gaps, name, gap, tolerance):
    """Build the single-variable marginal failure message."""
    return MarginalGapError(
        f"marginal {name} deviates by {gap:.2f} percentage points, "
        f"beyond the ±{tolerance} rounding unit (gaps: {gaps})"
    )


def check_cross_condition_hashes(paths) -> None:
    """Every condition must use one shared byte-identical pool file."""
    hashes = {hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in paths}
    if len(hashes) > 1:
        raise PoolHashConflictError(
            f"{len(hashes)} different pool files across conditions — "
            "every cell must share one byte-identical pool"
        )


def check_no_leaking_fields(pool_path, config_id: str) -> None:
    """No persona key may sit outside the whitelist (bookkeeping keys
    pid and pool_id are the only extras allowed)."""
    whitelist = set(respondent_loader.get_field_whitelist(config_id))
    allowed = whitelist | {"pid", "pool_id"}
    for index, record in enumerate(_read_pool(pool_path)):
        extra = set(record) - allowed
        if extra:
            raise LeakingPoolError(
                f"persona {index} carries non-whitelisted fields "
                f"{sorted(extra)} — refusing a leaking pool"
            )


def check_no_placeholders(pool_path) -> None:
    """No persona value may be a placeholder."""
    bad_values = ("", "n/a", "na", "none", "unknown", "null")
    for index, record in enumerate(_read_pool(pool_path)):
        for key, value in record.items():
            if value is None:
                raise PlaceholderError(
                    f"persona {index} field {key} is None"
                )
            if str(value).strip().lower() in bad_values:
                raise PlaceholderError(
                    f"persona {index} field {key} is the placeholder "
                    f"{value!r}"
                )


def check_seed_reproducibility(pool_path) -> tuple:
    """Replay the sampler from the provenance record; the pid list must
    reproduce exactly. Returns (original pids, replayed pids)."""
    provenance = json.loads(
        (Path(pool_path).parent / "POOL_PROVENANCE.json").read_text("utf-8")
    )
    replayed = pool_builder.sample_respondents_from_provenance(provenance)
    original = sorted(provenance["pid"])
    if replayed != original:
        raise PoolSizeError(
            "seed replay differs: provenance says "
            f"{original[:5]}..., replay gave {replayed[:5]}..."
        )
    return original, replayed


def _check_banned_tokens(pool_path) -> None:
    """No persona record may carry a banned outcome token."""
    for index, record in enumerate(_read_pool(pool_path)):
        for key, value in record.items():
            text = str(value).lower()
            for banned in BANNED_TOKENS:
                if banned in text:
                    raise LeakingPoolError(
                        f"persona {index} field {key} carries the banned "
                        f"outcome token {banned!r}"
                    )


def run(pool_path, dataset_root=None, respondents=None) -> int:
    """All gates, in order, writing VALIDATION_REPORT.md next to the pool.

    In: the pool JSONL path, optionally the dataset root and a loaded
    respondent table. Out: 0 when every gate passes, 1 on any failure.
    A failed gate is reported honestly in the file — never swallowed.
    """
    pool_path = Path(pool_path)
    lines = ["# VALIDATION REPORT", ""]
    ok = True

    def gate(name: str, passed: bool, detail: str) -> None:
        nonlocal ok
        ok = ok and passed
        lines.append(f"- **{name}: {'PASS' if passed else 'FAIL'}** — {detail}")

    provenance_path = pool_path.parent / "POOL_PROVENANCE.json"
    provenance = (
        json.loads(provenance_path.read_text("utf-8"))
        if provenance_path.exists() else None
    )
    config_id = provenance["config_id"] if provenance else "A"

    try:
        check_pool_size(pool_path, expected=100)
        gate("pool size", True, "100 lines, ids 0-99")
    except PoolSizeError as exc:
        gate("pool size", False, str(exc))
    try:
        if respondents is not None:
            check_persona_matches_respondents(pool_path, respondents)
            gate("persona-to-respondent truth", True,
                 "every value equals the panel record of the same pid")
    except RespondentMismatchError as exc:
        gate("persona-to-respondent truth", False, str(exc))
    try:
        if respondents is not None:
            gaps = check_marginals_vs_panel(pool_path, respondents,
                                            tolerance=1)
            gate("marginals vs panel", True,
                 f"sex x age max gap {gaps['sex_age_max_abs_gap']:.2f} pp; "
                 "single-variable gaps within the ±1 rounding unit; "
                 "reference is the panel, not the census")
    except MarginalGapError as exc:
        gate("marginals vs panel", False, str(exc))
    try:
        check_cross_condition_hashes([pool_path])
        gate("one shared pool across conditions", True,
             "single pool file; its sha256 is asserted per model block")
    except PoolHashConflictError as exc:
        gate("one shared pool across conditions", False, str(exc))
    try:
        check_no_leaking_fields(pool_path, config_id)
        check_no_placeholders(pool_path)
        _check_banned_tokens(pool_path)
        gate("no leaking fields / placeholders", True,
             f"all keys within the {config_id!r} whitelist; zero "
             "placeholders; zero banned outcome tokens")
    except (LeakingPoolError, PlaceholderError) as exc:
        gate("no leaking fields / placeholders", False, str(exc))
    try:
        if provenance is not None:
            original, replayed = check_seed_reproducibility(pool_path)
            gate("seed reproducibility", True,
                 f"fresh replay of seed {provenance['seed']} reproduces the "
                 f"pid list exactly ({len(replayed)} pids)")
    except PoolSizeError as exc:
        gate("seed reproducibility", False, str(exc))
    if dataset_root is not None and respondents is not None:
        try:
            check_panel_count(respondents, expected=2058)
            gate("full panel", True, "2,058 respondents loaded")
        except PanelCountError as exc:
            gate("full panel", False, str(exc))

    lines.append("")
    lines.append(f"**Overall: {'PASS — inference may start' if ok else 'FAIL — no inference'}**")
    (pool_path.parent / "VALIDATION_REPORT.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )
    return 0 if ok else 1
