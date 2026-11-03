# Registry-view tests: the merged inside-the-package view must combine the
# twin2k10r experiments, the restored six, and the T2KX expansion seventeen
# with the frozen counts, and expose a twin2k10-runner-compatible shape.
#   test_merged_registry_holds_31_grid_experiments
#   test_merged_registry_covers_38_grid_contrasts
#   test_restored_entries_match_run6_arm_structure — each restored entry's
#       arms and question ids equal the archived run6 leg structure.
#   test_entries_expose_runner_compatible_interface — name, arms, qids,
#       arm_qids behave like twin2k10's ExperimentSpec.
#   test_grid_membership_flags — base_rate and false_consensus are flagged
#       outside the frozen 31-experiment grid; every other entry inside.
#   test_restored_all_ready — all six restored experiments are READY and
#       none carries a withholding reason anymore.

from stimuli_restored.stimuli_restored_test_helpers import load_records


def test_merged_registry_holds_31_grid_experiments(restored_pkg):
    view = restored_pkg.merged_registry()
    grid = [entry for entry in view if entry["in_grid"]]
    assert len(grid) == 31
    names = {entry["name"] for entry in grid}
    for restored in restored_pkg.RESTORED_EXPERIMENT_NAMES:
        assert restored in names


def test_merged_registry_covers_38_grid_contrasts(restored_pkg):
    view = restored_pkg.merged_registry()
    assert sum(entry["n_contrasts"] for entry in view if entry["in_grid"]) == 38


def test_restored_entries_match_run6_arm_structure(
    restored_pkg, run6_root
):
    for entry in restored_pkg.merged_registry():
        if entry["source"] != "restored":
            continue
        path = (
            run6_root / "glm-4.7-flash"
            / f"{entry['name']}_blinded" / "records.jsonl"
        )
        archived: dict[str, set[str]] = {}
        for record in load_records(path):
            archived.setdefault(record["arm"], set()).add(record["qid"])
        mine = {arm: set(qids) for arm, qids in entry["arms"]}
        assert mine == archived, entry["name"]


def test_entries_expose_runner_compatible_interface(restored_pkg):
    from twin2k10.experiments import ExperimentSpec

    for entry in restored_pkg.merged_registry():
        spec = ExperimentSpec(
            entry["name"],
            arms=tuple((arm, tuple(qids)) for arm, qids in entry["arms"]),
        )
        assert spec.qids == tuple(
            qid for _arm, qids in entry["arms"] for qid in qids
        )
        for arm, qids in entry["arms"]:
            assert spec.arm_qids(arm) == tuple(qids)


def test_grid_membership_flags(restored_pkg):
    view = restored_pkg.merged_registry()
    outside = {entry["name"] for entry in view if not entry["in_grid"]}
    assert outside == {"base_rate", "false_consensus"}


def test_restored_all_ready(restored_pkg):
    for entry in restored_pkg.merged_registry():
        if entry["source"] == "restored":
            assert entry["status"] == "READY", entry["name"]
            assert entry["withheld_reason"] is None, entry["name"]


def test_counts_before_restoration(restored_pkg):
    counts = restored_pkg.coverage_counts(restored=False)
    assert counts == {
        "grid_experiments": 31,
        "grid_experiments_reachable": 25,
        "grid_contrasts": 38,
        "grid_contrasts_reachable": 28,
        "withheld_experiments": 6,
        "withheld_contrasts": 10,
    }
