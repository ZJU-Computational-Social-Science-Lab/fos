# This script renders the anonymized example prompts for the integration
# report: one experiment from each family (Twin-2K, ML1, ML2, TESS), each
# in both disclosure arms (blinded and unblinded), answered by persona 0
# of the adapted real-respondent pool. It writes INTEGRATION_PROMPTS.md
# next to itself and prints the file path. It runs no model calls — the
# prompts are rendered text only, and no respondent id (pid/pool_id)
# ever appears in the output.
from __future__ import annotations

import json
import sys
from pathlib import Path

_SCRIPTS = str(Path(__file__).resolve().parents[2])
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from twin2k10 import experiments as twin2k10_experiments
from twin2k10 import prompts as twin2k10_prompts
from twin2k10r import prompts as twin2k10r_prompts
from twin2k10r.integration import expansion_pool

# One representative experiment per family.
TWIN2K_EXPERIMENT = "allais"
EXPANSION_EXPERIMENTS = {
    "ML1": "T2KX-ml1_gamblers_fallacy",
    "ML2": "T2KX-ml2_hauser_s1",
    "TESS": "T2KX-howard823",
}


def _twin2k_section(source_record: dict) -> list[str]:
    """The Twin-2K family example: allais, both arms, item-level.

    twin2k10r renders from the dataset's own field names, so this
    section uses the source pool record directly (pid/pool_id stripped;
    the renderer skips keys it does not know, but never print them)."""
    persona = {
        key: value for key, value in source_record.items()
        if key not in expansion_pool.DROPPED_KEYS
    }
    experiment = twin2k10_experiments.EXPERIMENTS[TWIN2K_EXPERIMENT]
    arm_name = experiment.arms[0][0]
    item = twin2k10_experiments.arm_items(TWIN2K_EXPERIMENT, arm_name,
                                          twin2k10_experiments.load_stimuli())[0]
    sections = []
    for blinded, label in ((True, "blinded"), (False, "unblinded")):
        system = twin2k10r_prompts.build_system_prompt(
            TWIN2K_EXPERIMENT, blinded, informed_with_versions=not blinded
        )
        user = twin2k10r_prompts.build_user_prompt(
            persona, TWIN2K_EXPERIMENT, arm_name, item
        )
        sections.append(
            f"#### arm: {arm_name} ({label})\n\n"
            f"```\n=== SYSTEM ===\n{system}\n\n=== USER ===\n{user}\n```"
        )
    return [
        f"### Twin-2K family — `{TWIN2K_EXPERIMENT}`",
        *sections,
    ]


def _expansion_section(persona: dict, family: str, exp_id: str,
                       pipeline) -> list[str]:
    """One expansion family's example: first condition, both arms."""
    entry = pipeline.registry.get(exp_id)
    condition = entry.spec.conditions[0]
    sections = []
    for blinded, label in ((True, "blinded"), (False, "unblinded")):
        system = pipeline.prompts.build_system_prompt(exp_id, blinded)
        user = pipeline.prompts.build_user_prompt(
            persona, exp_id, condition.name, 0
        )
        sections.append(
            f"#### arm: {condition.name} ({label})\n\n"
            f"```\n=== SYSTEM ===\n{system}\n\n=== USER ===\n{user}\n```"
        )
    return [f"### {family} family — `{exp_id}`", *sections]


def render(out_path: Path, source_pool: Path) -> Path:
    """Render all four family sections and write the markdown file."""
    pipeline, personas = expansion_pool.expansion_personas(source_pool)
    sources = [
        json.loads(line)
        for line in source_pool.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    body: list[str] = [
        "# INTEGRATION_PROMPTS.md — rendered prompts with the adapted "
        "real-respondent pool",
        "",
        "One experiment per family, both disclosure arms, persona 0 of "
        "the adapted twin2k10r Config A pool (real Twin-2K-500 "
        "respondents; persona ids only, never pid/pool_id). Texts are "
        "the frozen stimuli of each pipeline, rendered verbatim by the "
        "pipeline's own prompt code — nothing was rewritten.",
        "",
        *_twin2k_section(sources[0]),
    ]
    for family, exp_id in EXPANSION_EXPERIMENTS.items():
        body.extend(_expansion_section(personas[0], family, exp_id, pipeline))
    out_path.write_text("\n\n".join(body) + "\n", encoding="utf-8")
    return out_path


if __name__ == "__main__":
    source = expansion_pool.SOURCE_POOL_PATH
    if not source.exists():
        raise SystemExit(f"source pool missing: {source}")
    print(render(Path(__file__).resolve().parent / "INTEGRATION_PROMPTS.md",
                 source))
