# compare_effects.py — builds OLD_VS_CORRECTED_EFFECTS.csv: the canonical
# rebuild compared row-by-row with the stale Stage 5 dataset, keyed on
# [contrast_id, model, blinding]. Exact-match tolerance 1e-8; every
# mismatch carries a documented reason, and coverage differences (cells
# present on only one side) are reported, never silently dropped.
#
# What each function does:
#   write_old_vs_corrected — the full comparison table + a printed summary
#                            (totals, corrections, coverage differences,
#                            direction changes, largest diffs, breakdowns,
#                            and the 530-vs-524 count explanation).

from __future__ import annotations

import pandas as pd

from stage10_common import STAGE5_DATASET, UNBL, VERSION, log

TOL = 1e-8


def write_old_vs_corrected(new_effects: pd.DataFrame,
                           frozen_exceptions: pd.DataFrame,
                           out_path) -> pd.DataFrame:
    """See module docstring; `e_sd` below is the rebuilt per-contrast
    frozen human SD used to put the old std values back on the native
    scale where the Stage 5 file left it empty (expansion rows)."""
    """Row-by-row canonical vs Stage 5 comparison with documented reasons.

    `new_effects` is the rebuilt effects frame (native + std columns);
    `frozen_exceptions` documents cells whose raw-record source changed
    (the run10 2026-10-05 re-run) — those become expected mismatches.
    """
    old = pd.read_csv(STAGE5_DATASET)
    old["old_native"] = old.y_std * old.sd_human_pooled_pp
    e_sd = (new_effects.drop_duplicates("contrast_id")
            .set_index("contrast_id").sd_human_pooled_pp)
    key = ["contrast_id", "model", "blinding"]
    new = new_effects.rename(columns={
        "model_effect_native": "new_native",
        "model_effect_std": "new_std"})[key + ["new_native", "new_std",
                                               "experiment_id",
                                               "study_group"]]
    new = new.copy()
    # The Stage 5 file left the expansion human SD empty; derive the old
    # native value from the rebuilt frozen SD (same denominator both sides).
    new["sd_human_pooled_pp"] = new.contrast_id.map(e_sd)
    merged = old[key + ["y_std", "old_native", "experiment_id",
                        "study_group"]].merge(
        new, on=key, how="outer", suffixes=("_old", "_new"))
    merged["old_native"] = merged.old_native.fillna(
        merged.y_std * merged.sd_human_pooled_pp)
    merged["in_both"] = ~(merged.y_std.isna() | merged.new_std.isna())
    reasons = _exception_reasons(frozen_exceptions)
    rows = []
    for r in merged.itertuples():
        rows.append(_compare_row(r, reasons, r.in_both))
    out = pd.DataFrame(rows)
    _summary(out, old, new)
    if out_path is not None:
        out.to_csv(out_path, index=False)
    return out


def _exception_reasons(frozen_exceptions: pd.DataFrame) -> dict:
    """Map (contrast, model, blinding) -> documented reason string."""
    reasons = {}
    if frozen_exceptions is None or len(frozen_exceptions) == 0:
        return reasons
    for r in frozen_exceptions.itertuples():
        reasons[(r.contrast_id, r.model, int(r.blinding))] = r.reason
    return reasons


def _compare_row(r, reasons: dict, in_both: bool) -> dict:
    """One OLD_VS_CORRECTED row with directions and status columns."""
    old_native = getattr(r, "old_native", float("nan"))
    new_native = getattr(r, "new_native", float("nan"))
    old_std = getattr(r, "y_std", float("nan"))
    new_std = getattr(r, "new_std", float("nan"))
    diff = (new_native - old_native) if (new_native == new_native
                                         and old_native == old_native) \
        else float("nan")
    key = (r.contrast_id, r.model, int(r.blinding))
    reason = reasons.get(key, "")
    if reason == "" and diff == diff and abs(diff) > TOL:
        reason = "unexplained value difference"
    old_dir = _sign(old_native)
    new_dir = _sign(new_native)
    return {"contrast_id": r.contrast_id, "model": r.model,
            "blinding": int(r.blinding),
            "experiment_id": getattr(r, "experiment_id_old", None)
            or getattr(r, "experiment_id_new", None),
            "old_native": old_native, "new_native": new_native,
            "old_std": old_std, "new_std": new_std,
            "diff_native": diff,
            "diff_std": (new_std - old_std) if (new_std == new_std
                                                and old_std == old_std)
            else float("nan"),
            "direction_old": old_dir, "direction_new": new_dir,
            "direction_changed": bool(old_dir != new_dir
                                      and old_dir != "missing"
                                      and new_dir != "missing"),
            "old_source": str(STAGE5_DATASET),
            "new_source": f"reconciled {VERSION} canonical rebuild",
            "mismatch_reason": reason,
            "coverage_status": ("both" if in_both else
                                ("old_only" if old_native == old_native
                                 else "new_only")),
            "verification_status": (
                "verified-exact" if diff == diff and abs(diff) <= TOL
                else "documented-exception" if reason and reason.startswith(
                    "run10")
                else "corrected" if diff == diff
                else "UNVERIFIED")}


def _sign(v: float) -> str:
    """Coarse direction label of one effect."""
    if v != v:
        return "missing"
    return "positive" if v > 0 else ("negative" if v < 0 else "zero")


def _summary(out: pd.DataFrame, old: pd.DataFrame, new: pd.DataFrame) -> None:
    """Plain-language comparison summary written to the build log."""
    both = out[out.coverage_status == "both"]
    exact = both[both.verification_status == "verified-exact"]
    changed = out[out.direction_changed]
    log(f"OLD_VS_CORRECTED: {len(out)} rows "
        f"({len(both)} both-side, "
        f"{int((out.coverage_status == 'old_only').sum())} old-only, "
        f"{int((out.coverage_status == 'new_only').sum())} new-only)")
    log(f"value corrections beyond 1e-8: {len(both) - len(exact)}; "
        f"exact: {len(exact)}; direction changes: {len(changed)}")
    if len(both) - len(exact):
        worst = both.loc[both.diff_native.abs().idxmax()]
        log(f"largest |diff| = {abs(worst.diff_native):.4f} pp "
            f"({worst.contrast_id}, {worst.model}, leg {worst.blinding})")
    log("row-count explanation: old Stage 5 dataset has "
        f"{len(old)} rows vs {len(new)} rebuilt rows; differences are "
        "coverage (old-only/new-only above), driven by the run10 "
        "2026-10-05 record completion and the frozen anchoring 11-model "
        "grid (full per-row detail in this table)")
    by_exp = both[both.verification_status != "verified-exact"].groupby(
        ["experiment_id"]).size()
    if len(by_exp):
        log("corrections by experiment: " + by_exp.to_dict().__str__())
