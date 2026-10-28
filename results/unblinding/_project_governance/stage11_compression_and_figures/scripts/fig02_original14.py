# fig02_original14.py — human and LLM response distributions for the 14
# ORIGINAL experiments (disease framing ... probability matching).
#
# What this file does: it reuses the validated distributional pipeline
# (publication_audit/distributional_error_explanation_20261019 scripts,
# seeded 20261010, built from the complete canonical records tree) to get
#   - per-arm individual-level human response codes (wave1_3, the
#     registered primary wave), and
#   - per-arm LLM response distributions per model and blinding condition
#     (persona-averaged category probabilities),
# all on each experiment's registered category scale.
#
# Functions:
#   load_original14 -> {exp_name: {arm_name: ArmData}} plus the
#                      experiment metadata list (contrasts, models,
#                      outcome type)

import sys
from dataclasses import dataclass

import numpy as np

AUDIT_SCRIPTS = ("/home/justin/Documents/ZJU work/fos/results/unblinding/"
                 "publication_audit/"
                 "distributional_error_explanation_20261019/scripts")
if AUDIT_SCRIPTS not in sys.path:
    sys.path.insert(0, AUDIT_SCRIPTS)

import exp_config as cfg  # noqa: E402
import human_data as hm  # noqa: E402
import llm_data as lm  # noqa: E402

from fig02_common import ArmData  # noqa: E402

CONDITIONS = ("blinded", "unblinded")
# the distributional audit's own eligibility: anchoring units are scored
# on the registered anchor more/less item only (documented there)
OUTCOME_TYPE = {
    "disease": "categorical (6-point favor scale)",
    "less_is_more": "ordinal (1-5 agreement)",
    "fire_extinguisher": "ordinal (1-5 agreement)",
    "seatbelt": "ordinal (1-6 likelihood)",
    "sunk_cost": "numerical (0-20 purchases)",
    "wta_wtp": "ordinal ($ bracket 1-10)",
    "allais": "binary choice",
    "linda": "ordinal (6-point probability rating)",
    "anchoring_redwood": "binary (anchor more/less)",
    "anchoring_african": "binary (anchor more/less)",
    "outcome_bias": "ordinal (1-7 evaluation)",
    "myside": "ordinal (1-6 ban support)",
    "prob_matching": "numerical grid (majority share /30)",
    "abs_relative": "binary choice",
}


@dataclass
class OriginalExp:
    """Everything Figure 02 needs about one original experiment."""
    name: str
    contrasts: list          # (contrast_name, control, treatment)
    models: list
    arms: dict               # arm_name -> ArmData
    outcome_type: str
    group: str = "original"


def load_original14() -> dict:
    """Load human codes + per-model LLM distributions for all 14 units."""
    human = hm.load_wave(cfg.HUMAN_W13, cfg.EXPERIMENTS)
    out = {}
    for exp in cfg.EXPERIMENTS:
        arms = {}
        for arm_name, arm in exp.arms.items():
            lo = float(arm.codes_start)
            hi = lo + arm.n_categories - 1
            points = np.arange(arm.n_categories, dtype=float) + lo
            llm_values, llm_weights = {}, {}
            for cond in CONDITIONS:
                for model in exp.models:
                    dists = lm.persona_category_dists(exp, arm, model, cond)
                    if not dists:
                        raise ValueError(
                            f"no LLM records: {exp.name}/{arm_name}/"
                            f"{model}/{cond}")
                    pooled = lm.persona_average(dists)
                    key = f"{model}|{cond}"
                    llm_values[key] = points
                    llm_weights[key] = pooled
            arms[arm_name] = ArmData(
                human_values=human[(exp.name, arm_name)],
                llm_values=llm_values, llm_weights=llm_weights,
                space=(lo, hi))
        out[exp.name] = OriginalExp(
            name=exp.name,
            contrasts=[(c.name, c.control, c.treatment)
                       for c in exp.contrasts],
            models=list(exp.models), arms=arms,
            outcome_type=OUTCOME_TYPE[exp.name])
    return out


if __name__ == "__main__":
    data = load_original14()
    for name, exp in data.items():
        ns = {a: len(d.human_values) for a, d in exp.arms.items()}
        print(name, len(exp.models), "models", ns)
