# Central settings for the five-model preliminary comparison.
#
# What this file does: it holds every path, model name, constant, and
# naming map the other scripts in this folder need, so the analysis can be
# re-run or re-pointed by editing one place. It also documents the two
# naming conventions this project uses for the disclosure conditions:
# run folders say "blinded"/"unblinded"; reports say "uninformed"
# (blinded) and "disclosure" (unblinded).
#
# What each name does:
#   MODELS           — the five models this preliminary comparison covers.
#   BLINDINGS        — run-folder condition labels, in report order.
#   CONDITION_LABELS — maps a run label to the report label.
#   OLD_* / NEW_*    — archived record locations (all READ-ONLY; the new
#                      production run is never written to).
#   TVD_PLAN         — per twin experiment: how to read the model's
#                      probability mass and which human reference card to
#                      compare it with (the historically validated plan).
#   SUPPORT          — the answer letters behind each mass kind above.
#   T2KX_HUMAN_FILES — per T2KX experiment: the cleaned human microdata
#                      file and how its condition wording maps onto the
#                      registry's condition names.
#   NEAR_ZERO_SD     — human effects smaller than this (in SD units) are
#                      flagged "near-zero human effect" and analyzed
#                      separately, per the project's convention.
#   SEED / N_DRAWS   — resampling settings (kept for reproducibility).

from pathlib import Path

# The five in-scope models (Phase 1 scope; all other models excluded).
MODELS = [
    "gpt-oss-20b",
    "gemma-4-26b-a4b",
    "gemma-4-31b-it-qat",
    "gemma-4-12b-it-qat",
    "qwen3.8-27b",
]

BLINDINGS = ["blinded", "unblinded"]
CONDITION_LABELS = {"blinded": "uninformed", "unblinded": "disclosure"}

# ------------------------------------------------------------------ paths
UNBL = Path("/home/justin/Documents/ZJU work/fos/results/unblinding")
MIRROR = Path("/home/justin/work/fos-data/results/unblinding")

# Historical twin runs (the "original" persona pools).
REGISTRY = UNBL / "T2K10-20260923T034851/experiment_registry.json"
OLD_RUN10 = MIRROR / "T2K10-20260923T034851"
OLD_RUN6 = UNBL / "TWIN2K_UNBLINDING_LOGPROBS_6TASKS-20260919T025143"
FROZEN_SIGNED = UNBL / ("T2K10-20260923T034851/final_audit/"
                        "blinding_signed_contrasts.csv")

# Historical expansion (T2KX) run + its frozen contrast table.
OLD_T2KX = UNBL / "expansion/work/T2KX-20261022T222604"
FROZEN_T2KX = UNBL / ("_project_governance/stage3_results/expansion17/"
                      "contrast_level_results.csv")

# Redesigned-pool production run (READ-ONLY).
NEW_RUN = Path("/home/justin/work/extended_runs/extended_run-20261103T151409")

# Human reference inputs.
CANONICAL = UNBL / ("_project_governance/stage10_data_reconciliation/data/"
                    "CANONICAL_MODEL_EFFECTS.csv")
CODEBOOK = Path("/home/justin/work/research/T2K10-FIGURES/"
                "contrast_feature_codebook.csv")
LABEL_CSV = Path("/home/justin/work/datasets/Twin-2K-500/"
                 "question_catalog_and_human_response_csv/"
                 "wave1_3_response_label.csv")
HUMAN_CLEAN = UNBL / "expansion/cleaned"

# Where outputs land (CSVs and figures; docs are written by a later task).
OUT = Path(__file__).resolve().parents[2] / ("results/unblinding/"
                                             "twin2k_redesign/"
                                             "five_model_preliminary")

# Twin TVD plan: (how to read model mass, which human card kind). The
# historically validated procedure compares probability MASS, never
# independent samples.
TVD_PLAN = {
    "allais": ("letters2", "dist"),
    "anchoring_redwood": ("letters2", "anchor"),
    "anchoring_african": ("letters2", "anchor"),
    "outcome_bias": ("letters7", "dist"),
    "myside": ("letters6", "dist"),
    "abs_relative": ("letters2", "dist"),
    "disease": ("p_safe", "p_safe"),
    "linda": ("digit6", "label_prob6"),
    "less_is_more": ("letters5", "label_likert5"),
    "fire_extinguisher": ("letters5", "label_likert5"),
    "seatbelt": ("letters6", "label_seat6"),
}
SUPPORT = {"letters2": "AB", "letters5": "ABCDE", "letters6": "ABCDEF",
           "letters7": "ABCDEFG"}

LIKERT5 = ["Disagree strongly", "Disagree a little",
           "Neither agree nor disagree", "Agree a little", "Agree strongly"]
PROB6 = ["Extremely improbable", "Very improbable", "Somewhat probable",
         "Moderately probable", "Very probable", "Extremely probable"]
SEAT6 = ["Disagree strongly", "Disagree a little",
         "Neither agree nor disagree", "Slightly agree", "Agree a little",
         "Agree strongly"]

# T2KX human microdata: file (v2 corrected microdata where it exists) and
# the wording each cleaned CSV uses for the registry's two conditions,
# in registry condition-name order. TVD is computed only for the
# single-item experiments whose human answer codes sit on exactly the
# same support as the model's registered outcome coding (checked at
# runtime); the TESS experiments and the multi-item experiments are
# excluded because no category-coded human distribution exists for them.
T2KX_HUMAN_FILES = {
    "T2KX-ml1_category_scales": (
        "ml1/ml1_category_scales.csv",
        ["low category scale", "high category scale"]),
    "T2KX-ml1_reciprocity": (
        "ml1/ml1_reciprocity.csv",
        ["US question asked second", "US question asked first"]),
    "T2KX-ml1_allowed_forbidden": (
        "ml1/ml1_allowed_forbidden_v2.csv",
        ["allow wording", "forbid wording"]),
    "T2KX-ml1_quote_attribution": (
        "ml1/ml1_quote_attribution.csv",
        ["disliked source (Bin Laden)", "liked source (Washington)"]),
    "T2KX-ml2_hauser_s1": (
        "ml2/ml2_hauser_s1_v2.csv",
        ["side-effect scenario", "greater-good scenario"]),
    "T2KX-ml2_risen_tempt_fate": (
        "ml2/ml2_risen_tempt_fate.csv",
        ["unprepared condition", "prepared condition"]),
    "T2KX-ml2_schwarz_order": (
        "ml2/ml2_schwarz_order.csv",
        ["life satisfaction asked first", "life satisfaction asked second"]),
    "T2KX-ml2_shafir_choose_reject": (
        "ml2/ml2_shafir_choose_reject.csv",
        ["choose whom to award custody", "choose whom to deny custody"]),
    "T2KX-ml2_miyamoto_correspondence": (
        "ml2/ml2_miyamoto_correspondence.csv",
        ["essay assigned pro-death penalty", "essay assigned pro-choice"]),
    "T2KX-ml2_rottenstreich_affect": (
        "ml2/ml2_rottenstreich_affect.csv",
        ["certainty outcome", "1% probability outcome"]),
    "T2KX-ml2_bauer_materialism": (
        "ml2/ml2_bauer_materialism.csv",
        ["consumer prime", "individual prime"]),
}

NEAR_ZERO_SD = 0.10
SEED = 20261106
N_DRAWS = 2000
