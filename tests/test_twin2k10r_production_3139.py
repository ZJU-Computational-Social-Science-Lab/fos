# Tests for the twin2k10r production runner (TASK-3139).
#
# WHAT THIS FILE CHECKS, in plain words:
#   - The model id map uses the reconciled names (the names the local
#     server actually answers to today), not the drifted historical ones.
#   - The run plan covers the merged 31-experiment registry (8 twin2k10r
#     grid experiments + 6 restored + 17 T2KX expansion experiments) and
#     runs the two flagged models (muse-glimmer, glm-4.7-flash) last.
#   - The twin-style driver runs one leg end to end against a MOCK model
#     server (choice scoring and digit scoring both exercised), writes
#     records with full provenance (run id, dataset hash, persona id,
#     prompt hash, status), and a resumed run skips every record already
#     on disk without duplicating anything (a torn tail line is never
#     counted as done).
#   - The expansion-style driver runs one T2KX leg against the same mock
#     server using the adapted real-respondent pool.
#   - The circuit breaker opens (with its own error type) after too many
#     consecutive failures instead of grinding on forever.
#
# All offline: the model server is a localhost mock in this file; the
# persona pool is injected; the only files written live in a temp dir.
import json
import math
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

_SCRIPTS = str(Path(__file__).resolve().parent.parent / "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from twin2k10r.integration.production import (  # noqa: E402
    driver_expansion,
    driver_twin,
    model_ids,
    run_plan,
    safeguards,
)


# ---------------------------------------------------------------- mock server
class _MockHandler(BaseHTTPRequestHandler):
    """HTTP verb dispatch into the mock server (passed as self.server)."""

    def do_GET(self) -> None:
        self.server.app._route(self)

    def do_POST(self) -> None:
        self.server.app._route(self)

    def log_message(self, *args) -> None:
        pass  # keep test output clean


class _MockLlamaServer:
    """A tiny stand-in for llama-server: /health, /v1/models and
    /v1/chat/completions with a canned first-token logprob payload."""

    def __init__(self, model_id: str, fail_first: int = 0):
        self.model_id = model_id
        self.fail_first = fail_first
        self.calls = 0
        self._lock = threading.Lock()
        self._server = HTTPServer(("127.0.0.1", 0), _MockHandler)
        self._server.app = self
        self.port = self._server.server_address[1]
        self._thread = threading.Thread(
            target=self._server.serve_forever, daemon=True
        )
        self._thread.start()

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()

    def _route(self, handler: BaseHTTPRequestHandler) -> None:
        with self._lock:
            self.calls += 1
            calls = self.calls
        if handler.path == "/health":
            return self._send(handler, 200, b'{"status":"ok"}')
        if handler.path == "/v1/models":
            payload = {"data": [{"id": self.model_id}]}
            return self._send(handler, 200, json.dumps(payload).encode())
        if handler.path == "/v1/chat/completions":
            if calls <= self.fail_first:
                return self._send(handler, 500, b'{"error":"boom"}')
            top = [
                {"token": "A", "logprob": -0.1},
                {"token": "B", "logprob": -2.0},
                {"token": "1", "logprob": -0.3},
                {"token": " 1", "logprob": -1.1},
                {"token": "The", "logprob": -0.5},
            ]
            block = {"token": "A", "logprob": -0.1, "top_logprobs": top}
            payload = {
                "model": self.model_id,
                "choices": [{
                    "message": {"content": "A"},
                    "logprobs": {"content": [block]},
                    "finish_reason": "stop",
                }],
            }
            return self._send(handler, 200, json.dumps(payload).encode())
        self._send(handler, 404, b"{}")

    def _send(self, handler: BaseHTTPRequestHandler, status: int,
              body: bytes) -> None:
        handler.send_response(status)
        handler.send_header("Content-Type", "application/json")
        handler.send_header("Content-Length", str(len(body)))
        handler.end_headers()
        handler.wfile.write(body)


# A two-persona stand-in pool with exactly the real dataset field names a
# Config A record carries (the drivers must render these, not legacy ones).
PERSONAS = [
    {
        "pid": "R001", "pool_id": 0, "age_bracket": "25-34",
        "gender": "female", "education": "bachelor",
        "household_income_bracket": "50-75k", "ethnicity": "white",
        "marital_status": "married", "household_size_bracket": "3-4",
    },
    {
        "pid": "R002", "pool_id": 1, "age_bracket": "35-44",
        "gender": "male", "education": "master",
        "household_income_bracket": "75-100k", "ethnicity": "asian",
        "marital_status": "single", "household_size_bracket": "1-2",
    },
]


@pytest.fixture()
def mock_server():
    server = _MockLlamaServer(model_id="qwen/qwen3-4b-2507")
    yield server
    server.stop()


# ------------------------------------------------------------------ model ids
def test_reconciled_model_id_for_qwen3_4b():
    assert model_ids.server_model_id("qwen3-4b") == "qwen/qwen3-4b-2507"


def test_reconciled_map_keeps_exact_matches_and_traps():
    assert model_ids.server_model_id("gpt-oss-20b") == "openai/gpt-oss-20b"
    assert (
        model_ids.server_model_id("granite-4.1-30b")
        == "lmstudio-community/granite-4.1-30b"
    )
    assert (
        model_ids.server_model_id("nemotron-cascade-2-30b-a3b")
        == "nvidia_nemotron-cascade-2-30b-a3b"
    )
    with pytest.raises(model_ids.UnknownModelError):
        model_ids.server_model_id("not-a-model")


# ------------------------------------------------------------------- run plan
def test_model_order_puts_flagged_models_last():
    models = run_plan.ordered_models()
    assert len(models) == 15
    assert set(run_plan.FLAGGED_MODELS) == {"muse-glimmer", "glm-4.7-flash"}
    assert models[-2:] == ["muse-glimmer", "glm-4.7-flash"]
    # The clean models keep the historical pinned order.
    clean = [m for m in models if not run_plan.is_flagged(m)]
    historical = [m for m in run_plan.HISTORICAL_MODEL_ORDER
                  if not run_plan.is_flagged(m)]
    assert clean == historical


def test_grid_plan_covers_merged_31_registry():
    twin = run_plan.twin_experiments()
    expansion = run_plan.expansion_experiments()
    assert len(twin) == 14  # 8 twin2k10r grid + 6 restored
    assert len(expansion) == 17
    assert len(set(twin) | set(expansion)) == 31


# ---------------------------------------------------------------- twin driver
def _run_twin_leg(tmp_path, server, experiment="disease", blinded=True):
    return driver_twin.run_leg(
        run_dir=tmp_path,
        model="qwen3-4b",
        base_url=server.base_url,
        experiment=experiment,
        blinded=blinded,
        personas=PERSONAS,
        run_id="EXT-TEST",
        dataset_sha256="abc123",
    )


def _records_of(path: Path) -> list[dict]:
    return [json.loads(line) for line in
            path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_twin_driver_runs_leg_against_mock_server(tmp_path, mock_server):
    written, total = _run_twin_leg(tmp_path, mock_server)
    path = tmp_path / "qwen3-4b" / "disease_blinded" / "records.jsonl"
    records = [json.loads(line) for line in
               path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert (written, total) == (len(records), len(records))
    assert written == 2 * len(dict(
        run_plan.twin_specs()["disease"].arms))  # 2 personas x 2 arms


def test_twin_records_carry_provenance_and_both_prompt_arms(
        tmp_path, mock_server):
    _run_twin_leg(tmp_path, mock_server)
    _run_twin_leg(tmp_path, mock_server, blinded=False)
    blinded_path = tmp_path / "qwen3-4b" / "disease_blinded" / "records.jsonl"
    unblinded_path = (
        tmp_path / "qwen3-4b" / "disease_unblinded" / "records.jsonl")
    for path in (blinded_path, unblinded_path):
        for record in (json.loads(line) for line in
                       path.read_text(encoding="utf-8").splitlines()
                       if line.strip()):
            assert record["run_id"] == "EXT-TEST"
            assert record["dataset_sha256"] == "abc123"
            assert record["persona_id"] in (0, 1)
            assert record["prompt_sha256"]
            assert record["status"] == "ok"
            assert record["model"] == "qwen3-4b"
    # Disclosure is design+versions only: the unblinded system prompt
    # names the randomization note, the blinded one is just the line.
    blinded = json.loads(blinded_path.read_text().splitlines()[0])
    unblinded = json.loads(unblinded_path.read_text().splitlines()[0])
    assert blinded["system_prompt"] == "You are a survey respondent."
    assert "randomly assigned" in unblinded["system_prompt"]
    assert blinded["system_prompt"] != unblinded["system_prompt"]


def test_twin_digit_scoring_yields_digit_distribution(tmp_path, mock_server):
    # sunk_cost's questions are text estimates (TE): digit items scored
    # on 0-9, the second scoring type beside choice letters.
    _run_twin_leg(tmp_path, mock_server, experiment="sunk_cost")
    path = tmp_path / "qwen3-4b" / "sunk_cost_blinded" / "records.jsonl"
    record = _records_of(path)[0]
    assert record["digit_items"], "sunk_cost is a numeric experiment"
    entry = record["digit_items"][0]
    assert entry["p_norm"] is not None
    assert "1" in entry["p_norm"]


def test_resume_skips_records_already_on_disk(tmp_path, mock_server):
    first = _run_twin_leg(tmp_path, mock_server)
    calls_after_first = mock_server.calls
    second = _run_twin_leg(tmp_path, mock_server)
    assert second == (0, first[1])
    assert mock_server.calls == calls_after_first  # zero new model calls


def test_torn_tail_is_never_counted_done(tmp_path, mock_server):
    _run_twin_leg(tmp_path, mock_server)
    path = tmp_path / "qwen3-4b" / "disease_blinded" / "records.jsonl"
    raw = path.read_bytes()
    path.write_bytes(raw[:-10])  # tear the last record mid-line
    written, _total = _run_twin_leg(tmp_path, mock_server)
    lines = [line for line in
             path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert written == 1  # only the torn record was re-run
    assert sum(1 for line in lines
               if json.loads(line)["persona_id"] == 1) == 2  # no duplicates


# ------------------------------------------------------------ expansion driver
def test_expansion_driver_runs_leg_with_adapted_pool(tmp_path, mock_server):
    from twin2k10r.integration.expansion_pool import write_adapted_pool

    def read_adapted_for_test(path):
        return [json.loads(line) for line in
                path.read_text(encoding="utf-8").splitlines() if line.strip()]

    # The expansion pipeline hard-requires exactly 100 records, so the
    # stand-in pool repeats the two test personas to that size.
    pool_path = tmp_path / "pool.jsonl"
    pool_path.write_text(
        "".join(
            json.dumps(persona, sort_keys=True) + "\n"
            for persona in PERSONAS * 50
        ),
        encoding="utf-8",
    )
    manifest = write_adapted_pool(
        pool_path, pool_path.with_name("adapted.jsonl"))
    adapted = read_adapted_for_test(pool_path.with_name("adapted.jsonl"))
    assert manifest["n"] == 100
    pipeline = driver_expansion.load_pipeline()
    exp_id = run_plan.expansion_experiments()[0]
    written, total = driver_expansion.run_leg(
        run_dir=tmp_path,
        pipeline=pipeline,
        model="qwen3-4b",
        base_url=mock_server.base_url,
        exp_id=exp_id,
        blinded=True,
        personas=adapted,
        run_id="EXT-TEST",
        dataset_sha256="abc123",
    )
    leg_dir = next((tmp_path / "qwen3-4b").glob(f"{exp_id}_blinded"))
    records = [json.loads(line) for line in
               leg_dir.joinpath("records.jsonl").read_text().splitlines()
               if line.strip()]
    assert written == total == len(records)
    assert written >= 2  # two adapted personas produced records
    record = records[0]
    assert record["run_id"] == "EXT-TEST"
    assert record["dataset_sha256"] == "abc123"
    assert record["prompt_sha256"]
    assert record["status"] == "ok"
    assert record["blind"] == "blinded"


# ------------------------------------------------------------------ safeguards
def test_circuit_breaker_opens_after_consecutive_failures():
    breaker = safeguards.CircuitBreaker(max_consecutive_failures=3)
    breaker.record_success()
    breaker.record_failure()
    breaker.record_failure()
    breaker.record_failure()
    with pytest.raises(safeguards.CircuitOpenError):
        breaker.check()


def test_circuit_breaker_resets_on_success():
    breaker = safeguards.CircuitBreaker(max_consecutive_failures=2)
    breaker.record_failure()
    breaker.record_success()
    breaker.record_failure()
    breaker.check()  # must NOT raise
