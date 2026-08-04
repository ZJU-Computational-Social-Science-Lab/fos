"""
Tests for the Phase 4 checkpointed runner: the SQLite state store, the
init / status / verify commands, and the run / retry execution loop. All
tests use an in-memory SQLite database so nothing touches the real
runs/state.db file, and result files are written to a pytest tmp dir.

Tests:
    test_init_is_idempotent          — seeding twice keeps 126 rows, not 252
    test_status_on_empty_db          — status works before any tables exist
    test_verify_detects_missing_file — verify reports a complete run whose
                                       result file is absent
    test_failed_run_does_not_block_subsequent_runs — one crashed run must
        not stop the runs after it
    test_network_mismatch_aborts_batch — a network that fails verification
        must abort the whole batch
    test_identity_stability — the same agent keeps its persona across runs
        but gets a different network degree
    test_no_cross_run_contamination — confederate prompts must not leak into
        later runs
    test_kill_mid_round2_and_resume — a run killed mid-round resumes without
        re-executing completed work
    test_resume_determinism — placement (confederates + permutation) is
        identical after an interrupt and restart
"""

import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "src"))

from fos.experiment import commands, deliberation, network, runner, store  # noqa: E402


class FakeLLMClient:
    """Canned-responses LLM client that never makes a network call.

    Records every call as an (agent_uid, round_index) tuple so tests can
    count calls per agent per round. Can raise a RuntimeError on the first
    N calls or on specific (agent_uid, round_index) pairs, which lets tests
    simulate a run crashing mid-deliberation.
    """

    def __init__(self, response_text="PLACEHOLDER", fail_n_calls=0, fail_on=None):
        self.response_text = response_text
        self.fail_n_calls = fail_n_calls
        self.fail_on = fail_on  # callable(agent_uid, round_index) -> bool
        self.calls = []  # list of (agent_uid, round_index) tuples
        self._raised = set()  # (agent_uid, round_index) pairs that already raised

    def chat(self, messages, json_mode=False, max_tokens=None):
        """Return the canned response, raising when a failure was configured.

        A fail_on failure fires at most once per (agent_uid, round_index)
        pair, so a killed run can resume and finish the interrupted call.
        """
        system = messages[0]["content"]
        uid = system.split("agent_uid=")[1].split()[0]
        round_index = int(system.split("round_index=")[1].split()[0])
        self.calls.append((uid, round_index))
        if self.fail_n_calls > 0:
            self.fail_n_calls -= 1
            raise RuntimeError("FakeLLMClient injected failure")
        if (
            self.fail_on is not None
            and self.fail_on(uid, round_index)
            and (uid, round_index) not in self._raised
        ):
            self._raised.add((uid, round_index))
            raise RuntimeError(f"FakeLLMClient failure for {uid} round {round_index}")
        return self.response_text


@pytest.fixture
def db():
    """An in-memory SQLite database with the tables created and seeded."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    store.init_db(conn)
    store.seed_from_csv(conn)
    yield conn
    conn.close()


@pytest.fixture
def results_dir(tmp_path, monkeypatch):
    """Point result-file writes at a temp dir so tests never touch runs/."""
    monkeypatch.setattr(runner, "RESULTS_DIR", tmp_path)
    return tmp_path


def test_init_is_idempotent(db):
    """Initialising and seeding twice must keep 126 rows, not 252."""
    store.init_db(db)
    store.seed_from_csv(db)
    count = db.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
    assert count == 126


def test_status_on_empty_db():
    """The status command must work before any tables exist."""
    conn = sqlite3.connect(":memory:")
    try:
        summary = commands.status(conn)
        assert summary["total"] == 126
        assert summary["complete"] == 0
        assert summary["pending"] == 0
    finally:
        conn.close()


def test_verify_detects_missing_file(db):
    """A run marked complete with no result file on disk must be reported."""
    store.mark_complete("run_079", "runs/results/run_079.json", db)
    report = commands.verify_runs(db)
    assert "run_079" in report["missing"]


def test_failed_run_does_not_block_subsequent_runs(db, results_dir, monkeypatch):
    """A run that crashes mid-run is marked failed; the next runs still execute.

    A broken implementation that aborted the whole batch on any error would
    leave run_123 and run_048 pending with no result files.
    """
    fake = FakeLLMClient(fail_n_calls=1)
    monkeypatch.setattr(deliberation, "_agent_client", lambda agent: fake)
    commands.run(limit=3, conn=db)
    by_id = {r["run_id"]: r for r in store.list_runs(conn=db)}
    assert by_id["run_079"]["status"] == "failed"
    assert "FakeLLMClient injected failure" in by_id["run_079"]["last_error"]
    assert by_id["run_123"]["status"] == "complete"
    assert by_id["run_048"]["status"] == "complete"
    assert (results_dir / "run_123.json").exists()
    assert (results_dir / "run_048.json").exists()
    assert not (results_dir / "run_079.json").exists()


def test_network_mismatch_aborts_batch(db, tmp_path, monkeypatch):
    """A network that fails verification aborts the whole batch.

    The first pending run (run_079, config 11 / un_veto) is checked against
    corrupted statistics. A broken implementation that kept going would
    execute run_123 and run_048 despite the corrupted stats.
    """
    lines = network.NETWORK_STATS_PATH.read_text(encoding="utf-8").splitlines()
    header, rows = lines[0], lines[1:]
    corrupted = [header]
    for line in rows:
        if line.startswith("11,un_veto,"):
            parts = line.split(",")
            parts[5] = "999.0"  # mean_degree
            line = ",".join(parts)
        corrupted.append(line)
    bad = tmp_path / "network_stats.csv"
    bad.write_text("\n".join(corrupted) + "\n", encoding="utf-8")
    monkeypatch.setattr(network, "NETWORK_STATS_PATH", bad)

    commands.run(limit=3, conn=db)
    by_id = {r["run_id"]: r for r in store.list_runs(conn=db)}
    assert by_id["run_079"]["status"] == "running"  # aborted mid-run, not failed
    assert by_id["run_123"]["status"] == "pending"  # never reached
    assert by_id["run_048"]["status"] == "pending"


def test_identity_stability(db, results_dir):
    """The same agent keeps its persona across runs; its degree changes.

    run_079 and run_048 both use pop_b1 but different holme_kim configs.
    A broken implementation that regenerated personas per run would show
    different big_five values for the same agent_uid across the two runs.
    """
    commands.run(run_id="run_079", conn=db)
    commands.run(run_id="run_048", conn=db)
    first = json.loads((results_dir / "run_079.json").read_text(encoding="utf-8"))
    second = json.loads((results_dir / "run_048.json").read_text(encoding="utf-8"))
    agents_first = {a["agent_uid"]: a for a in first["agents"]}
    agents_second = {a["agent_uid"]: a for a in second["agents"]}
    assert set(agents_first) == set(agents_second)
    for uid, record in agents_first.items():
        assert record["big_five"] == agents_second[uid]["big_five"]
        assert record["voting_model"] == agents_second[uid]["voting_model"]
    changed = [
        uid
        for uid in agents_first
        if agents_first[uid]["degree"] != agents_second[uid]["degree"]
    ]
    assert changed, "degree should differ between configs (holme_kim m=4 vs m=3)"


def test_no_cross_run_contamination(db, results_dir):
    """Confederate prompts in run 1 must not leak into run 2's prompts.

    pop_b1_agent_011 is a confederate in run_079 but not in run_048. A
    broken implementation that mutated the shared population configs
    instead of deep-copying them would inject confederate text into the
    later run's prompt.
    """
    commands.run(run_id="run_079", conn=db)
    commands.run(run_id="run_048", conn=db)
    first = json.loads((results_dir / "run_079.json").read_text(encoding="utf-8"))
    second = json.loads((results_dir / "run_048.json").read_text(encoding="utf-8"))
    conf_first = {c["agent_id"] for c in first["confederates"]}
    conf_second = {c["agent_id"] for c in second["confederates"]}
    only_first = sorted(conf_first - conf_second)
    assert only_first, "need an agent that is a confederate in run 1 but not run 2"
    agent_x = only_first[0]

    calls_first = store.get_agent_calls("run_079", 1, conn=db)
    calls_second = store.get_agent_calls("run_048", 1, conn=db)
    prompt_first = json.loads(
        next(c["response_json"] for c in calls_first if c["agent_uid"] == agent_x)
    )["prompt"]
    prompt_second = json.loads(
        next(c["response_json"] for c in calls_second if c["agent_uid"] == agent_x)
    )["prompt"]
    # Run 1 injected the confederate prompt; run 2 must be clean.
    assert any(
        phrase in prompt_first for phrase in ("genuinely support", "genuinely oppose")
    )
    assert "genuinely support" not in prompt_second
    assert "genuinely oppose" not in prompt_second


def test_kill_mid_round2_and_resume(db, results_dir, monkeypatch):
    """A run killed mid-round-2 resumes without re-executing completed work.

    The fake client raises when round 2 reaches the 51st agent, so round 1
    and the first 50 round-2 agents are recorded. A broken implementation
    that ignored the store's agent_calls would re-call every round-1 and
    completed round-2 agent on resume.
    """
    population = json.loads(
        (runner.POPULATIONS_DIR / "pop_b1.json").read_text(encoding="utf-8")
    )
    target = population["agents"][50]["agent_id"]  # 51st agent in round-2 order
    fake = FakeLLMClient(fail_on=lambda uid, rnd: rnd == 2 and uid == target)
    monkeypatch.setattr(deliberation, "_agent_client", lambda agent: fake)

    commands.run(limit=1, conn=db)  # attempt 1: fails mid-round-2
    assert store.get_run("run_079", conn=db)["status"] == "failed"
    attempt1 = Counter(fake.calls)
    assert sum(1 for uid, rnd in attempt1 if rnd == 1) == 100  # round 1 complete
    # Round 2: 50 completed calls plus the failing call (recorded before it raised).
    assert sum(1 for uid, rnd in attempt1 if rnd == 2) == 51

    commands.retry(conn=db)
    commands.run(limit=1, conn=db)  # attempt 2: resumes and completes
    assert store.get_run("run_079", conn=db)["status"] == "complete"
    final = Counter(fake.calls)

    # Round 1 was not re-executed: every round-1 call appears exactly once.
    for uid, rnd in attempt1:
        if rnd == 1:
            assert final[(uid, 1)] == 1
    # Completed round-2 agents (all but the failing one) were not re-executed.
    for uid, rnd in attempt1:
        if rnd == 2 and uid != target:
            assert final[(uid, 2)] == 1
    # The failing agent was retried and completed on the resume.
    assert final[(target, 2)] == 2
    # Every round ended with a full 100-agent call set.
    for round_idx in (1, 2, 3):
        assert len(store.get_agent_calls("run_079", round_idx, conn=db)) == 100
    assert (results_dir / "run_079.json").exists()


def test_resume_determinism(db, results_dir, monkeypatch):
    """Placement (confederates + permutation) is identical after a restart.

    The fake client fails on the very first call, so the run is interrupted
    right after placement. A broken implementation that used a fresh random
    seed on every attempt would produce a different confederate set or node
    permutation when the run resumes.
    """
    fake = FakeLLMClient(fail_n_calls=1)  # interrupt right after placement
    monkeypatch.setattr(deliberation, "_agent_client", lambda agent: fake)

    commands.run(limit=1, conn=db)  # attempt 1 fails mid-round-1
    assert store.get_run("run_079", conn=db)["status"] == "failed"
    placement_first = json.loads(
        next(
            c["response_json"]
            for c in store.get_agent_calls("run_079", 0, conn=db)
            if c["agent_uid"] == "_placement"
        )
    )

    commands.retry(conn=db)
    commands.run(limit=1, conn=db)  # attempt 2 resumes and completes
    assert store.get_run("run_079", conn=db)["status"] == "complete"
    result = json.loads((results_dir / "run_079.json").read_text(encoding="utf-8"))

    assert result["node_permutation"] == placement_first["node_permutation"]
    assert result["placement_seed"] == placement_first["placement_seed"]
    assert {c["agent_id"]: c["stance"] for c in result["confederates"]} == {
        c["agent_id"]: c["stance"] for c in placement_first["confederates"]
    }
