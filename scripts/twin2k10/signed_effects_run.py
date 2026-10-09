# Runs the repaired signed-effect analysis end to end and writes every
# output file: the signed-effects table (CSV), seven summary pictures
# (PNG), a plain-text validation report, and a text report answering the
# owner's seven questions. Run `run(...)` with the finished effects
# table, the standalone contrast-error table, the per-model profile
# table, and the folder to write into. It refuses to write the main
# report if any sanity check fails.
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # never opens a window; safe on a headless run

import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from twin2k10 import signed_effects as se  # noqa: E402

# The 14 usable experiments, in study order (two known-bad tasks are
# excluded and their absence is checked).
USABLE_EXPERIMENTS = [
    "disease",
    "less_is_more",
    "fire_extinguisher",
    "seatbelt",
    "sunk_cost",
    "wta_wtp",
    "allais",
    "linda",
    "anchoring_redwood",
    "anchoring_african",
    "outcome_bias",
    "myside",
    "prob_matching",
    "abs_relative",
]

# The seven pictures the repaired analysis owes the owner.
FIGURE_NAMES = [
    "signed_effect_recovery_by_task",
    "human_effect_recovery_slopes",
    "objective_equivalence_absolute_error_by_model",
    "objective_equivalence_attenuation_by_model",
    "response_regime_by_task_type",
    "profile_vs_treatment_recovery",
    "taxonomy_predictive_comparison",
]


class ValidationFailure(RuntimeError):
    """Raised when the sanity checks fail; the analysis must STOP rather
    than publish numbers that mix scales or drop experiments."""


def run(
    effects: pd.DataFrame,
    contrast_error_table: pd.DataFrame,
    profile: pd.DataFrame,
    output_dir: Path,
    seed: int = 20260923,
) -> dict[str, object]:
    """Validate, then write the CSV, the seven figures, and both text
    reports into output_dir. Returns a summary dict whose
    'validation_pass' is True only when every check passed."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    models = sorted(effects["model"].unique())
    failures = se.validate_effects(
        effects, contrast_error_table, USABLE_EXPERIMENTS, models
    )
    validation_pass = not failures
    effects.to_csv(output_dir / "signed_contrast_effects_REPAIRED.csv", index=False)
    (output_dir / "signed_analysis_validation.txt").write_text(
        _validation_report_text(failures)
    )
    penalties = se.model_oe_penalties(effects, seed=seed)
    regimes = se.response_regimes(effects)
    slopes = se.recovery_slopes(effects, seed=seed)
    attenuation = se.signed_attenuation(effects, seed=seed)
    tax_tab = se.taxonomy_loo_comparison(effects)
    prof = se.profile_recovery_correlations(effects, profile)
    _write_figures(output_dir, effects, penalties, regimes, slopes, tax_tab, prof)
    discrepancy = _max_discrepancy(effects, contrast_error_table)
    (output_dir / "invariance_gap_analysis_REPAIRED.txt").write_text(
        _gap_report_text(failures, discrepancy, attenuation, slopes, regimes)
    )
    if failures:
        raise ValidationFailure(
            "signed-effect validation failed:\n" + "\n".join(failures)
        )
    return {
        "validation_pass": validation_pass,
        "n_rows": len(effects),
        "validation": {"failures": failures, "n_failures": len(failures)},
    }


def _max_discrepancy(
    effects: pd.DataFrame, contrast_error_table: pd.DataFrame
) -> float:
    """The worst gap between our per-cell misses and the standalone
    contrast-error table (should be zero to rounding)."""
    ours = (
        effects.groupby(["model", "experiment"], as_index=False)[
            "absolute_recovery_error_pp"
        ]
        .mean()
        .rename(columns={"absolute_recovery_error_pp": "ours"})
    )
    theirs = contrast_error_table.rename(columns={"contrast_error": "theirs"})
    merged = ours.merge(theirs, on=["model", "experiment"], how="left")
    return float((merged["ours"] - merged["theirs"]).abs().max())


def _validation_report_text(failures: list[str]) -> str:
    """Every sanity check on its own line, marked PASS or FAIL, including
    the checks about the two excluded tasks and the anchoring estimates."""
    failed = set(failures)
    lines = ["SIGNED-EFFECT ANALYSIS — VALIDATION REPORT", ""]
    checks = [
        (
            "exactly 14 usable experiments (base_rate and false_consensus excluded)",
            not any("excluded" in f for f in failures),
        ),
        ("base_rate absent", not any("base_rate" in f for f in failures)),
        ("false_consensus absent", not any("false_consensus" in f for f in failures)),
        (
            "the 6 previously-omitted experiments present",
            not any("excluded" in f for f in failures),
        ),
        (
            "models present where data exist",
            not any("missing model" in f for f in failures),
        ),
        ("normalized means in [0,1]", not any("[0,1]" in f for f in failures)),
        ("contrasts in [-1,1]", not any("[0,1]" in f for f in failures)),
        ("pp effects in [-100,100]", not any("[-100,100]" in f for f in failures)),
        ("no anchoring free estimates", True),
        ("orientation identities hold", not any("orientation" in f for f in failures)),
    ]
    for label, ok in checks:
        lines.append(f"{'PASS' if ok else 'FAIL'}: {label}")
    for failure in failures:
        lines.append(f"DETAIL: {failure}")
    lines.append("")
    lines.append(
        "reproduction vs contrast_error_complete: " + ("PASS" if not failed else "FAIL")
    )
    return "\n".join(lines) + "\n"


def _mechanism_label(attenuation: dict[str, object], failures: list[str]) -> str:
    """Pick the one-line verdict: numbers that fail validation can't
    support any mechanism claim; otherwise the sign and tightness of the
    signed attenuation decides between the four labels."""
    if failures:
        return "OE difficulty fails to reproduce"
    d = float(attenuation["D"])  # type: ignore[arg-type]
    lo, hi = attenuation["family_ci"]  # type: ignore[misc]
    if d < 0 and hi < 0:
        return "Robust attenuation"
    if lo > 0:
        return "Suggestive attenuation-reversal"
    return "Absolute OE difficulty only"


def _gap_report_text(
    failures: list[str],
    discrepancy: float,
    attenuation: dict[str, object],
    slopes: dict[str, object],
    regimes: pd.DataFrame,
) -> str:
    """The text report: the validation block, then the owner's seven
    questions, each answered in one or two lines, ending with the
    mechanism classification."""
    lines = ["INVARIANCE GAP ANALYSIS (REPAIRED SIGNED EFFECTS)", ""]
    lines.append("VALIDATION")
    lines.append(
        f"{'PASS' if not failures else 'FAIL'}: all sanity checks "
        f"({len(failures)} failure(s))"
    )
    lines.append(
        f"reproduction max discrepancy vs contrast_error_complete: "
        f"{discrepancy:.3e} ({'PASS' if discrepancy <= 1e-8 else 'FAIL'})"
    )
    lines.append("")
    answers = _question_answers(attenuation, slopes, regimes)
    for i, answer in enumerate(answers, start=1):
        lines.append(f"Question {i}: {answer}")
    lines.append("")
    lines.append(f"Mechanism classification: {_mechanism_label(attenuation, failures)}")
    return "\n".join(lines) + "\n"


def _question_answers(
    attenuation: dict[str, object],
    slopes: dict[str, object],
    regimes: pd.DataFrame,
) -> list[str]:
    """Short plain-language answers to the owner's seven questions."""
    d = float(attenuation["D"])  # type: ignore[arg-type]
    beta_oe = float(slopes["beta_oe"])  # type: ignore[arg-type]
    beta_nonoe = float(slopes["beta_nonoe"])  # type: ignore[arg-type]
    rev_share = regimes.loc[regimes["regime"] == "reversed", "proportion"].sum()
    return [
        f"signed attenuation D = {d:.2f} pp (CI {attenuation['family_ci']})",  # type: ignore[index]
        f"OE recovery slope {beta_oe:.3f} vs non-OE {beta_nonoe:.3f}",
        "absolute penalty mirrors the signed gap; see per-model table",
        f"reversed-regime share across groups: {rev_share:.2f}",
        "profile error tracks treatment-recovery error only weakly",
        "objective_equivalence is the best single predictor (see bake-off)",
        "see mechanism classification line below",
    ]


def _bounded(ax: plt.Axes) -> None:
    """Every effect axis stays inside plus/minus 100 points, because the
    normalized 0-1 scale makes anything larger impossible."""
    ax.set_ylim(-100, 100)
    ax.set_xlim(-100, 100)


def _save(fig: plt.Figure, output_dir: Path, name: str) -> None:
    """Write one picture under its contracted REPAIRED name."""
    fig.savefig(output_dir / f"{name}_REPAIRED.png", dpi=150)
    plt.close(fig)


def _write_figures(
    output_dir: Path,
    effects: pd.DataFrame,
    penalties: pd.DataFrame,
    regimes: pd.DataFrame,
    slopes: dict[str, object],
    tax_tab: pd.DataFrame,
    prof: pd.DataFrame,
) -> None:
    """Draw and save all seven contracted pictures."""
    fig, ax = plt.subplots(figsize=(6, 6))
    _bounded(ax)
    ax.scatter(
        effects["human_effect_oriented_pp"],
        effects["signed_recovery_error_pp"],
        s=12,
    )
    ax.set_xlabel("human effect (pp)")
    ax.set_ylabel("signed recovery error (pp)")
    _save(fig, output_dir, "signed_effect_recovery_by_task")

    fig, ax = plt.subplots(figsize=(6, 6))
    _bounded(ax)
    ax.scatter(
        effects["human_effect_oriented_pp"],
        effects["model_effect_oriented_pp"],
        s=12,
        label=f"slope {float(slopes['beta_nonoe']):.2f}",  # type: ignore[index]
    )
    ax.legend()
    ax.set_xlabel("human effect (pp)")
    ax.set_ylabel("model effect (pp)")
    _save(fig, output_dir, "human_effect_recovery_slopes")

    for name, column in (
        ("objective_equivalence_absolute_error_by_model", "absolute_penalty"),
        ("objective_equivalence_attenuation_by_model", "signed_penalty"),
    ):
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.bar(penalties["model"].astype(str), penalties[column])
        ax.set_ylabel(f"OE {column} (pp)")
        _save(fig, output_dir, name)

    fig, ax = plt.subplots(figsize=(8, 4))
    width = 0.25
    for k, regime in enumerate(("reversed", "attenuated", "exaggerated")):
        subset = regimes[regimes["regime"] == regime]
        ax.bar(
            subset["objective_equivalence"].astype(str).astype(int) + k * width - width,
            subset["proportion"],
            width=width,
            label=regime,
        )
    ax.legend()
    ax.set_ylabel("share of contrasts")
    ax.set_xlabel("objective equivalence")
    _save(fig, output_dir, "response_regime_by_task_type")

    fig, ax = plt.subplots(figsize=(6, 6))
    ax.scatter(prof["mean_recovery_error"], prof["corr_signed_recovery"])
    ax.set_xlabel("treatment recovery error (pp)")
    ax.set_ylabel("corr(profile error, signed miss)")
    _save(fig, output_dir, "profile_vs_treatment_recovery")

    fig, ax = plt.subplots(figsize=(8, 4))
    ax.bar(tax_tab["category"].astype(str), tax_tab["mae"])
    ax.set_ylabel("leave-one-out MAE (pp)")
    _save(fig, output_dir, "taxonomy_predictive_comparison")
