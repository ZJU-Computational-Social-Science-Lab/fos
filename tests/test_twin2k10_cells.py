# Locked tests for the twin2k10 study's cell enumeration, record identity,
# and resume/durability contract (TASK-2139 RED phase; tests ONLY — no
# implementation lives yet, so every test here errors at collection until
# scripts/twin2k10/cells.py exists).
#
# WHAT THIS FILE CHECKS, in plain words:
#   - One record is one (model, persona, experiment, arm, blinding) cell.
#     The grid follows twin2k6 semantics: 15 models x 100 personas (0-99)
#     x arms x 2 blinding arms. The 10 experiments have 19 arms together
#     (nine 2-arm experiments + false_consensus's single within-subject
#     arm), so the study holds 5,700 cells per model / 57,000 total.
#   - Enumeration is deterministic (same order every call, seed 42) and
#     every cell key is unique.
#   - Resume: cells already present in records.jsonl (matched by key) are
#     skipped — proven with a counting fake transport. Each finished
#     record is appended with its 5 identity fields before the next cell
#     starts, so a crash never loses finished work.
#
# All offline: pure enumeration plus a temp file; no network, no models.
import json
import sys
from pathlib import Path

import pytest

# The launch scripts live in scripts/ and are not on pytest's pythonpath.
_SCRIPTS = str(Path(__file__).resolve().parent.parent / "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from twin2k10 import cells, config, experiments  # noqa: E402

# Arms per experiment, straight from the study's own loaded stimuli.
_ARM_NAMES = {
    (entry["experiment"], entry["arm"])
    for entry in experiments.load_stimuli().values()
}
N_ARMS = len(_ARM_NAMES)                     # 19 = 9 x 2-arms + 1 single
PER_MODEL = config.PERSONA_COUNT * N_ARMS * len(config.BLINDINGS)   # 3,800
TOTAL = len(config.MODELS) * PER_MODEL       # 57,000


def _record_from(cell: tuple) -> dict:
    """Build a minimal record dict carrying one cell's identity (helper)."""
    model, persona_id, experiment, arm, blind = cell
    return {
        "model": model, "persona_id": persona_id, "experiment": experiment,
        "arm": arm, "blind": blind,
    }


def _counting_transport(calls: list) -> object:
    """A fake scoring transport that records every call (helper)."""

    def transport(cell: tuple) -> dict:
        calls.append(cell)
        return {"succeeded": True}

    return transport


def test_expected_totals_follow_from_the_stimuli_grid() -> None:
    """5,700 records per model, 57,000 total — derived from the stimuli."""
    assert cells.EXPECTED_RECORDS_PER_MODEL == PER_MODEL == 3800
    assert cells.EXPECTED_RECORDS_TOTAL == TOTAL == 57000
    assert N_ARMS == 19
    assert cells.EXPECTED_RECORDS_TOTAL == len(config.MODELS) * cells.EXPECTED_RECORDS_PER_MODEL


def test_enumeration_lists_all_cells_in_a_fixed_order() -> None:
    """enumerate_cells lists 57,000 cells and never changes between calls."""
    first = cells.enumerate_cells()
    assert len(first) == TOTAL
    assert first == cells.enumerate_cells()


def test_seed_42_is_the_study_design_seed() -> None:
    """Determinism is pinned by the shared seed: config.SEED == 42."""
    assert config.SEED == 42


def test_every_cell_key_is_unique() -> None:
    """No two cells share the same 5-part identity."""
    keys = [cells.record_key(cell) for cell in cells.enumerate_cells()]
    assert len(keys) == TOTAL
    assert len(set(keys)) == TOTAL


def test_cell_shape_is_model_persona_experiment_arm_blind() -> None:
    """A cell is a 5-tuple drawn from the study's own grid values."""
    cell = cells.enumerate_cells()[0]
    assert isinstance(cell, tuple) and len(cell) == 5
    model, persona_id, experiment, arm, blind = cell
    assert model in config.MODELS
    assert isinstance(persona_id, int) and 0 <= persona_id < 100
    assert experiment in experiments.EXPERIMENTS
    assert blind in ("blinded", "unblinded")


def test_grid_covers_every_experiment_arm_persona_and_blinding() -> None:
    """Every (experiment, arm) × 100 personas × 2 blinds × 15 models."""
    all_cells = cells.enumerate_cells()
    assert {c[1] for c in all_cells} == set(range(100))
    assert {c[4] for c in all_cells} == {"blinded", "unblinded"}
    assert {(c[2], c[3]) for c in all_cells} == _ARM_NAMES
    for exp_name in experiments.EXPERIMENTS:
        subset = [c for c in all_cells if c[2] == exp_name]
        arm_names = {arm for (experiment, arm) in _ARM_NAMES
                     if experiment == exp_name}
        assert len(subset) == 15 * 100 * len(arm_names) * 2, exp_name


def test_false_consensus_contributes_half_the_cells_of_a_two_arm_experiment() -> None:
    """19 arms: false_consensus (1 arm) = 3,000 cells, each 2-arm = 6,000."""
    all_cells = cells.enumerate_cells()
    fc = [c for c in all_cells if c[2] == "false_consensus"]
    allais = [c for c in all_cells if c[2] == "allais"]
    assert len(fc) == 15 * 100 * 1 * 2
    assert len(allais) == 15 * 100 * 2 * 2


def test_subset_enumeration_by_passing_just_one_model() -> None:
    """Asking for one model yields exactly that model's 3,800 cells."""
    subset = cells.enumerate_cells(models=[config.MODELS[0]])
    assert len(subset) == PER_MODEL
    assert {cell[0] for cell in subset} == {config.MODELS[0]}


def test_record_key_reads_cells_and_records_but_rejects_other_types() -> None:
    """record_key: cells pass through, records are read, junk raises."""
    cell = cells.enumerate_cells()[0]
    assert cells.record_key(cell) == cell
    assert cells.record_key(_record_from(cell)) == cell
    with pytest.raises(TypeError):
        cells.record_key("not a cell")


def test_resume_skips_cells_already_on_disk() -> None:
    """A rerun calls the transport only for cells not yet in records.jsonl."""
    import tempfile
    all_cells = cells.enumerate_cells(models=[config.MODELS[0]],
                                      personas=[0, 1],
                                      experiments_map={
                                          "allais":
                                              experiments.EXPERIMENTS["allais"]
                                      })
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "records.jsonl"
        calls: list = []
        cells.run_cells(all_cells, _counting_transport(calls), path)
        assert len(calls) == len(all_cells)
        calls.clear()
        cells.run_cells(all_cells, _counting_transport(calls), path)
        assert calls == []


def test_records_on_disk_carry_their_cell_identity() -> None:
    """Every written record is stamped with its 5 identity fields."""
    import tempfile
    planned = cells.enumerate_cells(models=[config.MODELS[0]],
                                    personas=[0],
                                    experiments_map={
                                        "allais":
                                            experiments.EXPERIMENTS["allais"]
                                    })
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "records.jsonl"
        cells.run_cells(planned, _counting_transport([]), path)
        lines = path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == len(planned)
        for cell, line in zip(planned, lines):
            record = json.loads(line)
            assert cells.record_key(record) == cells.record_key(cell)


# --------------------------------------------------------------------------
# TASK-2150 RED tests — review blocker B1 (RESULT-2146): a multi-row
# record must carry `expected_rows` (the answered item's own statement
# count, read from the shipped stimuli) so the preflight can tell a
# complete 10-row answer from a truncated one. The records here are
# built through the real record builder with fake scorer/sampler calls
# — no network, no models.
# --------------------------------------------------------------------------


def _offline_multi_record(experiment: str, arm: str,
                          answer_rows: int) -> dict:
    """One real multi-row cell's record with every fake call healthy."""
    from twin2k10 import legexec

    context = legexec.LegContext(
        model=config.MODELS[0],
        model_id=f"offline-{config.MODELS[0]}",
        base_url="http://127.0.0.1:8080",
        personas=[{"persona_id": 0}],
        stimuli=experiments.load_stimuli(),
        inference=legexec.inference_settings("http://127.0.0.1:8080"),
    )
    answer = "\n".join(
        f"{row}. {row * 10}" for row in range(1, answer_rows + 1)
    )

    def fake_sampler(messages: list) -> dict:
        return {"samples": [answer] * config.NUMERIC_SAMPLES_K,
                "first_top_logprobs": [], "calls_failed": 0,
                "errors": [], "elapsed_seconds": 0.0}

    def fake_scorer(messages: list) -> dict:
        return {"top_logprobs": [], "decision_position": 0,
                "skipped_prefix": [], "skipped_len": 0, "succeeded": True}

    cell = (config.MODELS[0], 0, experiment, arm, "blinded")
    return legexec.execute_cell(context, fake_scorer, fake_sampler, cell)


def test_multi_numeric_records_carry_the_item_row_count_as_expected_rows() -> None:
    """false_consensus answers a 10-row item, so its record says 10."""
    record = _offline_multi_record("false_consensus", "all", answer_rows=10)
    assert record.get("expected_rows") == 10, (
        "a multi-row record must carry expected_rows (its item's row "
        "count) so the preflight can catch truncated answers"
    )


def test_expected_rows_reads_each_items_own_row_count() -> None:
    """problem1's item has 10 rows and problem2's has 6 — no hardcoding."""
    ten_rows = _offline_multi_record("prob_matching", "problem1",
                                     answer_rows=10)
    six_rows = _offline_multi_record("prob_matching", "problem2",
                                     answer_rows=6)
    assert ten_rows.get("expected_rows") == 10
    assert six_rows.get("expected_rows") == 6
