# fig02_expansion.py — human and LLM response distributions for the 17
# EXPANSION experiments (Many Labs 1/2 replications + 4 TESS studies).
#
# What this file does: it builds, per experiment and arm, the same kind of
# registered-scale response samples the original-14 module produces:
#   - human: individual-level respondents from the cleaned ML1/ML2 files
#     and the TESS .sav studies, coded by each study's registered outcome
#     coding (cleaned dv columns are already on the registered scale;
#     TESS answers are re-binned with the same conventions the LLM
#     pipeline registered);
#   - LLM: one value per persona (per-persona mean over scored items)
#     streamed from the COMPLETE production records of the expansion run
#     (the Stage 10-verified authoritative source, primary retention cut
#     branch_mass >= 0.80; zero/low-mass records are missing, never 0).
#
# Functions:
#   load_expansion      -> {exp_id: ExpansionExp} with per-arm ArmData
#   _load_llm           -> streams records for one experiment
#   _human_ml1_ml2      -> reads the cleaned tidy CSVs
#   _human_tess         -> reads the three TESS .sav studies

import json
import math
import sys
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

UNBL = ("/home/justin/Documents/ZJU work/fos/results/unblinding")
EXPANSION_DIR = f"{UNBL}/expansion"
EXPANSION_RUN = f"{EXPANSION_DIR}/work/T2KX-20261022T222604"

sys.path.insert(0, EXPANSION_DIR)
from pipeline import outcomes as po  # noqa: E402
from pipeline import registry as pr  # noqa: E402

from fig02_common import ArmData  # noqa: E402

CONDITIONS = ("blinded", "unblinded")


@dataclass
class ExpansionExp:
    """Everything Figure 02 needs about one expansion experiment."""
    exp_id: str
    contrasts: list          # (contrast_name, control, treatment)
    models: list
    arms: dict = field(default_factory=dict)   # arm name -> ArmData
    outcome_type: str = ""
    group: str = ""


# registered contrasts (contrast_id, control, treatment) per experiment;
# arm conditions per _project_governance/stage3_methodology/CONTRAST_REGISTER
SPECS = {
    "T2KX-ml1_gamblers_fallacy": dict(
        group="ML1", type="numerical (sqrt rolls, registered buckets)",
        contrasts=[("three_sixes_minus_two_sixes", "two_sixes",
                    "three_sixes")],
        human_csv=("ml1", "ml1_gamblers_fallacy.csv",
                   {"two sixes (one die shows 3)": "two_sixes",
                    "three sixes": "three_sixes"}),
        human_fn="gamblers"),
    "T2KX-ml1_category_scales": dict(
        group="ML1", type="binary (share above 2.5 h)",
        contrasts=[("high_scale_minus_low_scale", "low_scale",
                    "high_scale")],
        human_csv=("ml1", "ml1_category_scales.csv",
                   {"low category scale": "low_scale",
                    "high category scale": "high_scale"})),
    "T2KX-ml1_reciprocity": dict(
        group="ML1", type="binary (let reporters in)",
        contrasts=[("us_first_minus_us_second", "us_second", "us_first")],
        human_csv=("ml1", "ml1_reciprocity.csv",
                   {"US question asked second": "us_second",
                    "US question asked first": "us_first"})),
    "T2KX-ml1_allowed_forbidden": dict(
        group="ML1", type="binary (opposes speeches, corrected v2 coding)",
        contrasts=[("forbid_minus_allow", "allow_wording",
                    "forbid_wording")],
        human_csv=("ml1", "ml1_allowed_forbidden_v2.csv",
                   {"allow wording": "allow_wording",
                    "forbid wording": "forbid_wording"})),
    "T2KX-ml1_quote_attribution": dict(
        group="ML1", type="ordinal (1-9 agreement, reversed)",
        contrasts=[("liked_minus_disliked", "disliked_source",
                    "liked_source")],
        human_csv=("ml1", "ml1_quote_attribution.csv",
                   {"disliked source (Bin Laden)": "disliked_source",
                    "liked source (Washington)": "liked_source"})),
    "T2KX-ml1_imagined_contact": dict(
        group="ML1", type="ordinal (1-9 intention)",
        contrasts=[("imagined_contact_minus_control", "control_walk",
                    "imagined_contact")],
        human_csv=("ml1", "ml1_imagined_contact.csv",
                   {"control": "control_walk",
                    "imagined contact": "imagined_contact"})),
    "T2KX-ml2_hauser_s1": dict(
        group="ML2", type="binary (permissible)",
        contrasts=[("greater_good_minus_side_effect", "side_effect",
                    "greater_good")],
        human_csv=("ml2", "ml2_hauser_s1_v2.csv",
                   {"side-effect scenario": "side_effect",
                    "greater-good scenario": "greater_good"})),
    "T2KX-ml2_risen_tempt_fate": dict(
        group="ML2", type="ordinal (1-10 likelihood)",
        contrasts=[("prepared_minus_unprepared", "unprepared",
                    "prepared")],
        human_csv=("ml2", "ml2_risen_tempt_fate.csv",
                   {"unprepared condition": "unprepared",
                    "prepared condition": "prepared"})),
    "T2KX-ml2_schwarz_order": dict(
        group="ML2", type="ordinal (1-11 life satisfaction)",
        contrasts=[("life_second_minus_life_first", "life_first",
                    "life_second")],
        human_csv=("ml2", "ml2_schwarz_order.csv",
                   {"life satisfaction asked first": "life_first",
                    "life satisfaction asked second": "life_second"})),
    "T2KX-ml2_shafir_choose_reject": dict(
        group="ML2", type="binary (Parent A vs B choice)",
        contrasts=[("deny_minus_award", "award_framing", "deny_framing")],
        human_csv=("ml2", "ml2_shafir_choose_reject.csv",
                   {"choose whom to award custody": "award_framing",
                    "choose whom to deny custody": "deny_framing"})),
    "T2KX-ml2_miyamoto_correspondence": dict(
        group="ML2", type="ordinal (1-15 inferred attitude)",
        contrasts=[("pro_choice_minus_pro_death", "essay_pro_death",
                    "essay_pro_choice")],
        human_csv=("ml2", "ml2_miyamoto_correspondence.csv",
                   {"essay assigned pro-death penalty": "essay_pro_death",
                    "essay assigned pro-choice": "essay_pro_choice"})),
    "T2KX-ml2_rottenstreich_affect": dict(
        group="ML2", type="binary choice (movie star vs $50)",
        contrasts=[("one_percent_minus_certainty", "certainty",
                    "one_percent")],
        human_csv=("ml2", "ml2_rottenstreich_affect.csv",
                   {"certainty outcome": "certainty",
                    "1% probability outcome": "one_percent"})),
    "T2KX-ml2_bauer_materialism": dict(
        group="ML2", type="ordinal (1-7 trust)",
        contrasts=[("individual_minus_consumer", "consumer_prime",
                    "individual_prime")],
        human_csv=("ml2", "ml2_bauer_materialism.csv",
                   {"consumer prime": "consumer_prime",
                    "individual prime": "individual_prime"})),
}


def _registered_space(exp_id: str) -> tuple:
    """The experiment's registered outcome-space bounds, read from the
    frozen pipeline outcome codings (never invented by hand)."""
    po._build()
    entry = po._INDEX[exp_id]
    outs = [entry["single"]] if "single" in entry else list(
        entry["multi"].values())
    values = [letter.value for o in outs for letter in o.coding]
    return (float(min(values)), float(max(values)))


def _persona_means(path: str, exp_id: str, item_filter=None) -> dict:
    """Stream one production leg: per-persona mean registered value.

    item_filter — optional (item_index -> bool) so item-specific contrasts
    (budescu) keep only their registered items. Retention rule = the
    registered primary cut (branch_mass >= 0.80); excluded records are
    counted, never folded in.
    """
    persona_items: dict = {}
    n_total = n_excluded = 0
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            n_total += 1
            if item_filter is not None and not item_filter(
                    rec["item_index"]):
                continue
            mass = rec.get("branch_mass")
            mass = float(mass) if mass is not None else 0.0
            if mass < 0.80:
                n_excluded += 1
                continue
            outcome = po.outcome_for(exp_id, rec["condition"],
                                     rec["item_index"])
            value = outcome.value_of(rec["p_norm"])
            persona_items.setdefault(rec["persona_id"], []).append(value)
    means = {p: float(np.mean(v)) for p, v in persona_items.items()}
    return {"means": means, "n_total": n_total, "n_excluded": n_excluded}


def _gamblers_human(dv: np.ndarray) -> np.ndarray:
    """Registered floor convention: rolls floored into the 0-10 buckets,
    then the sqrt scale the LLM buckets carry (the registered rebin)."""
    rolls = np.floor(np.asarray(dv, dtype=float) ** 2)
    rolls = np.clip(rolls, 0.0, 10.0)
    return np.sqrt(rolls)


def _load_llm(exp_id: str, models: list, item_filter=None) -> dict:
    """{model|condition: persona-mean array} for one experiment."""
    out = {}
    for model in models:
        for cond in CONDITIONS:
            path = (f"{EXPANSION_RUN}/{model}/{exp_id}_{cond}/"
                    "records.jsonl")
            got = _persona_means(path, exp_id, item_filter)
            if not got["means"]:
                raise ValueError(f"no retained records: {path}")
            out[f"{model}|{cond}"] = got
    return out


def _build_standard(spec: dict, exp_id: str) -> ExpansionExp:
    """Human (cleaned CSV) + LLM (records) for a standard experiment."""
    subdir, fname, label_map = spec["human_csv"]
    df = pd.read_csv(f"{EXPANSION_DIR}/cleaned/{subdir}/{fname}")
    df = df.dropna(subset=["dv"])
    lo, hi = _registered_space(exp_id)
    exp = ExpansionExp(
        exp_id=exp_id, contrasts=list(spec["contrasts"]),
        models=_models(), outcome_type=spec["type"], group=spec["group"])
    llm = _load_llm(exp_id, exp.models)
    llm_values = {k: np.clip(np.array(list(v["means"].values())), lo, hi)
                  for k, v in llm.items()}
    for reg_name, label in ((v, k) for k, v in label_map.items()):
        vals = df.loc[df.condition == label, "dv"].to_numpy(float)
        if spec.get("human_fn") == "gamblers":
            vals = _gamblers_human(vals)
        outside = int(np.sum((vals < lo - 1e-9) | (vals > hi + 1e-9)))
        if outside:
            raise ValueError(
                f"{exp_id}/{reg_name}: {outside} human values outside the "
                f"registered space [{lo}, {hi}] — coding mismatch")
        vals = np.clip(vals, lo, hi)
        exp.arms[reg_name] = ArmData(human_values=vals,
                                     llm_values=llm_values, space=(lo, hi))
    return exp


_MODELS_CACHE = None


def _models() -> list:
    global _MODELS_CACHE
    if _MODELS_CACHE is None:
        from pipeline import config as pc
        _MODELS_CACHE = list(pc.MODELS)
    return _MODELS_CACHE


def load_expansion() -> dict:
    """All 17 expansion experiments (13 standard + 4 TESS)."""
    po._build()
    out = {}
    for exp_id, spec in SPECS.items():
        out[exp_id] = _build_standard(spec, exp_id)
    from fig02_tess import load_tess
    out.update(load_tess())
    return out


if __name__ == "__main__":
    data = load_expansion()
    for name, exp in data.items():
        ns = {a: len(d.human_values) for a, d in exp.arms.items()}
        print(exp.group, name, len(exp.models), "models", ns)
