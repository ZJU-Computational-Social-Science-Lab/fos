# Parity tests: prove the restored stimuli, contrasts, and scoring are
# byte-for-byte and number-for-number identical to the frozen history.
#   test_restored_text_matches_archived_prompt — each restored question text
#       appears verbatim inside its archived run6 user prompt.
#   test_restored_options_match_archived_prompt — each restored option string
#       appears verbatim as the option's lettered line in the same prompt.
#   test_generated_file_matches_catalog — the checked-in generated stimuli
#       file equals a fresh programmatic extraction from the catalog.
#   test_restored_contrasts_match_frozen_registry — every restored contrast
#       row (experiment, contrast name, treatment, control) equals the
#       frozen experiment registry's row for the same contrast id.
#   test_scoring_reproduces_archived_expected — the ported scoring rule
#       reproduces every archived record's expected_response on every
#       retained record of every restored leg.
import csv
import json

import pytest

from stimuli_restored.stimuli_restored_test_helpers import (
    archived_prompt_options,
    load_records,
)


def _archived_record(run6_record_factory, stimulus: dict) -> dict:
    """The archived blinded record for one stimulus entry."""
    records = load_records(
        run6_record_factory(stimulus["experiment"], "blinded")
    )
    matching = [
        r for r in records
        if r["arm"] == stimulus["arm"] and r["qid"] == stimulus["qid"]
    ]
    assert matching, f"no archived record for {stimulus['qid']}"
    return matching[0]


def test_restored_text_matches_archived_prompt(restored_pkg, run6_record_factory):
    for stimulus in restored_pkg.restored_stimuli():
        record = _archived_record(run6_record_factory, stimulus)
        assert stimulus["question_text"] in record["user_prompt"], (
            f"{stimulus['qid']} text not verbatim in archived prompt"
        )


def test_restored_options_match_archived_prompt(restored_pkg, run6_record_factory):
    for stimulus in restored_pkg.restored_stimuli():
        record = _archived_record(run6_record_factory, stimulus)
        options = stimulus.get("options") or []
        prompt_options = archived_prompt_options(record["user_prompt"])
        if not options:
            # The two open-numeric sunk_cost questions carry no catalog
            # options, but the archived prompts render the 0-20 answer
            # brackets as a lettered list; that rendering must match.
            assert prompt_options == [str(n) for n in range(21)], (
                f"{stimulus['qid']} archived prompt not the 0-20 bracket list"
            )
            continue
        for option in options:
            assert option in prompt_options, (
                f"{stimulus['qid']} option {option!r} not verbatim in prompt"
            )


def test_generated_file_matches_catalog(restored_pkg, catalog_path):
    fresh = restored_pkg.extract_from_catalog(catalog_path)
    on_disk = json.loads(
        restored_pkg.STIMULI_FILE.read_text(encoding="utf-8")
    )
    assert fresh == on_disk["stimuli"]


def test_restored_contrasts_match_frozen_registry(restored_pkg, registry_csv):
    with registry_csv.open(encoding="utf-8", newline="") as handle:
        frozen = {row["contrast_id"]: row for row in csv.DictReader(handle)}
    for contrast in restored_pkg.RESTORED_CONTRASTS:
        row = frozen[contrast["contrast_id"]]
        assert contrast["experiment_id"] == row["experiment_id"], contrast["contrast_id"]
        assert contrast["contrast_name"] == row["contrast_name"], contrast["contrast_id"]
        assert contrast["treatment_condition"] == row["treatment_condition"], (
            contrast["contrast_id"]
        )
        assert contrast["control_condition"] == row["control_condition"], (
            contrast["contrast_id"]
        )


def test_scoring_reproduces_archived_expected(restored_pkg, run6_root):
    checked = 0
    for experiment in restored_pkg.RESTORED_EXPERIMENT_NAMES:
        for blinding in ("blinded", "unblinded"):
            path = (
                run6_root / "glm-4.7-flash" / f"{experiment}_{blinding}"
                / "records.jsonl"
            )
            for record in load_records(path):
                if not record.get("succeeded", False):
                    continue
                mine = restored_pkg.record_outcome(record, experiment)
                assert mine is not None, f"unscored retained record {record['qid']}"
                # The disease outcome is the "safe" share (p_safe_norm);
                # every other restored outcome is the record's expected
                # response on its native scale.
                expected = (
                    record["p_safe_norm"] if experiment == "disease"
                    else record["expected_response"]
                )
                assert abs(mine - expected) < 1e-9, (
                    f"{experiment} scoring disagrees with archived record "
                    f"{record['qid']} persona {record['persona_id']}"
                )
                checked += 1
    assert checked > 3000, f"parity pass covered only {checked} records"


def test_withheld_experiments_absent_from_twin2k10(restored_pkg):
    from twin2k10 import experiments

    for name in restored_pkg.RESTORED_EXPERIMENT_NAMES:
        assert name not in experiments.EXPERIMENTS, (
            f"{name} already present in the frozen twin2k10 registry"
        )


@pytest.mark.parametrize(
    "experiment,arm,qid",
    [
        ("disease", "gain", "QID157"),
        ("disease", "loss", "QID158"),
        ("less_is_more", "A", "QID171"),
        ("less_is_more", "B", "QID172"),
        ("less_is_more", "C", "QID173"),
        ("fire_extinguisher", "all", "QID174"),
        ("fire_extinguisher", "98pct", "QID175"),
        ("fire_extinguisher", "95pct", "QID176"),
        ("seatbelt", "all", "QID177"),
        ("seatbelt", "98pct", "QID178"),
        ("seatbelt", "95pct", "QID179"),
        ("sunk_cost", "no_card", "QID181"),
        ("sunk_cost", "card", "QID182"),
        ("wta_wtp", "wtp_certainty", "QID189"),
        ("wta_wtp", "wta_certainty", "QID190"),
        ("wta_wtp", "wtp_noncertainty", "QID191"),
    ],
)
def test_every_archived_arm_exists_with_expected_qid(
    restored_pkg, run6_root, experiment, arm, qid
):
    path = (
        run6_root / "glm-4.7-flash" / f"{experiment}_blinded" / "records.jsonl"
    )
    arms = load_records(path)
    matching = [r for r in arms if r["arm"] == arm]
    assert matching and all(r["qid"] == qid for r in matching)
