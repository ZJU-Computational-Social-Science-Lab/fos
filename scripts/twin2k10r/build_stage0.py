# This script builds the STAGE0 run artifacts: the real Config A pool
# (seed 42, n=100) and the Config B pool, their provenance records, the
# dataset manifest, the validation report, and the example-prompt
# document. Run it after the dataset mirror is in place:
#   python scripts/twin2k10r/build_stage0.py
# It writes everything under scripts/twin2k10r/runs/STAGE0/ and exits
# non-zero if any validation gate fails.
import sys
from pathlib import Path

# The study packages live in scripts/, which is not on sys.path by default.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from twin2k10r import config, dataset_manifest, example_prompts
from twin2k10r import pool_builder, respondent_loader, validate_pool

STAGE0 = Path(__file__).resolve().parent / "runs" / "STAGE0"


def build_pool(config_id: str, out_dir: Path) -> dict:
    """Build one pool + provenance + manifest copy inside out_dir."""
    manifest_file = out_dir / "dataset_manifest.json"
    manifest_file.parent.mkdir(parents=True, exist_ok=True)
    if not manifest_file.exists():
        dataset_manifest.write_manifest(config.DATASET_ROOT, manifest_file)
    dataset_manifest.verify_manifest(config.DATASET_ROOT, manifest_file)
    respondents = respondent_loader.load_respondents(
        config.DATASET_ROOT, config_id
    )
    pids = pool_builder.sample_respondents(
        respondents, n=config.PERSONA_COUNT, seed=config.SEED
    )
    provenance = pool_builder.write_pool(
        pids, respondents, config_id, out_dir / "pools"
        / "twin2k_respondent.jsonl"
    )
    return provenance


def write_examples_doc() -> None:
    """PROMPT_EXAMPLES.md — the 10 anonymized prompts, Config A + B."""
    lines = [
        "# PROMPT EXAMPLES — 10 rendered, anonymized prompts",
        "",
        "Exactly what the model sees. The real respondent id is replaced by the",
        "pool id (0-99). Config A renders 7 real demographic fields;",
        "Config B adds the MEASURED TRAITS block. Study results never",
        "appear in any prompt of any arm.",
        "",
    ]
    for config_id, subdir in (("A", "pools"), ("B", "pools_B")):
        run_dir = STAGE0 if subdir == "pools" else STAGE0 / "config_B"
        examples = example_prompts.build_example_prompts(run_dir, config_id)
        lines.append(f"## Config {config_id}")
        for example in examples:
            lines += [
                "",
                f"### pool_id {example['pool_id']} — "
                f"{example['arm']} arm — {example['stimulus_type']} — "
                f"disclosure variant: "
                f"{example['disclosure_variant'] or 'n/a (blinded)'}",
                "",
                "**System prompt:**",
                "",
                "```",
                example["system_prompt"],
                "```",
                "",
                "**User prompt:**",
                "",
                "```",
                example["prompt"],
                "```",
            ]
    (STAGE0 / "PROMPT_EXAMPLES.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


def main() -> int:
    """Build both pools, validate both, write the example document."""
    prov_a = build_pool("A", STAGE0)
    config_b_dir = STAGE0 / "config_B"
    prov_b = build_pool("B", config_b_dir)
    respondents = respondent_loader.load_respondents(
        config.DATASET_ROOT, "A"
    )
    code_a = validate_pool.run(
        STAGE0 / "pools" / "twin2k_respondent.jsonl",
        dataset_root=config.DATASET_ROOT, respondents=respondents,
    )
    code_b = validate_pool.run(
        config_b_dir / "pools" / "twin2k_respondent.jsonl",
        dataset_root=config.DATASET_ROOT, respondents=respondents,
    )
    write_examples_doc()
    print(f"Config A pool sha256 {prov_a['pool_sha256'][:12]}..., "
          f"validation exit {code_a}")
    print(f"Config B pool sha256 {prov_b['pool_sha256'][:12]}..., "
          f"validation exit {code_b}")
    return code_a or code_b


if __name__ == "__main__":
    sys.exit(main())
