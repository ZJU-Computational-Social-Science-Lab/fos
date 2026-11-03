# This file renders a handful of complete example prompts for human
# inspection — exactly what a model would see, with the real pid
# replaced by the pool id (0-99) so no person is identifiable. The ten
# examples cover both arms (blinded and unblinded), several stimulus
# types (a choice question, a rating statement, a numeric estimate),
# both disclosure variants (uninformed, informed-with-versions), and
# work for both pool configurations (A and B).
# Functions:
#   build_example_prompts — the list of ten anonymized example dicts.
import json
from pathlib import Path

from twin2k10 import experiments
from twin2k10r import prompts

# The pool file every run shares.
POOL_FILENAME = "twin2k_respondent.jsonl"

# (experiment, arm, item index, blinded, informed_with_versions) for the
# ten examples, chosen to cover arms, stimulus types and variants.
_EXAMPLE_PLAN = [
    ("allais", "form1", 0, True, False),
    ("linda", "conjunction", 0, True, False),
    ("base_rate", "30_engineers", 0, True, False),
    ("myside", "ford", 0, True, False),
    ("false_consensus", "all", 0, True, False),
    ("allais", "form2", 0, False, False),
    ("outcome_bias", "success", 0, False, True),
    ("base_rate", "70_engineers", 0, False, True),
    ("linda", "no_conjunction", 1, False, False),
    ("prob_matching", "problem2", 0, False, True),
]


def _stimulus_type(item: dict) -> str:
    """The human-readable kind of one item: a lettered choice, a rating
    statement, or a bare numeric estimate."""
    if item["kind"] == "choice":
        return "choice"
    return "rating" if item.get("statement") is not None else "numeric"


def build_example_prompts(run_dir, config_id: str) -> list:
    """Ten fully rendered, anonymized example prompts.

    In: the run directory (holding pools/twin2k_respondent.jsonl) and
    the pool config id. Out: a list of ten dicts, each carrying the pool
    id, arm, stimulus type, disclosure variant, system prompt and the
    fully rendered user prompt. No real pid appears anywhere.
    """
    pool_path = Path(run_dir) / "pools" / POOL_FILENAME
    pool = [json.loads(line) for line in
            pool_path.read_text("utf-8").splitlines() if line.strip()]
    stimuli = experiments.load_stimuli()
    examples = []
    for index, (experiment, arm, item_index, blinded,
                informed) in enumerate(_EXAMPLE_PLAN):
        persona = pool[index]
        items = experiments.arm_items(experiment, arm, stimuli)
        item = items[item_index]
        examples.append({
            "pool_id": persona["pool_id"],
            "experiment": experiment,
            "experiment_arm": arm,
            "blinded": blinded,
            "arm": "blinded" if blinded else "unblinded",
            "stimulus_type": _stimulus_type(item),
            "disclosure_variant": (
                None if blinded
                else ("informed_with_versions" if informed else "uninformed")
            ),
            "config_id": config_id,
            "system_prompt": prompts.build_system_prompt(
                experiment, blinded, informed
            ),
            "prompt": prompts.build_user_prompt(
                persona, experiment, arm, item
            ),
        })
    return examples
