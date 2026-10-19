"""Tests that a restarted run never duplicates a finished sample.

We simulate a crash in the middle of a cell: some records are already
on disk, the runner is restarted, and every already-collected
idempotency key must be skipped exactly once — with nothing appended
twice.
"""

import json

import runner
import transport as t


class FakeTransport:
    """A transport stub that records which samples it was asked for."""

    def __init__(self):
        self.calls = 0

    def __call__(self, payload, model, route, sleep=lambda _s: None):
        self.calls += 1
        return t.RawResponse(
            200,
            {
                "choices": [
                    {
                        "message": {"content": '{"reason": "r", "amount": 17}'},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 100, "completion_tokens": 10},
                "model": model,
            },
        )


def _write(path, record):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")


def _config():
    config = runner.default_config("engineering")
    config["games"] = {"1120": {"variants": ["basic"]}}
    config["arms"] = ["no_persona"]
    config["models"] = ["deepseek-v4-flash"]
    return config


def test_restart_never_duplicates_samples(tmp_path):

    config = _config()
    names = [f"p{i}" for i in range(5)]
    plan = runner.build_plan(config, names, seed=1)
    assert len(plan) == 10
    out_dir = tmp_path / "out"
    fake = FakeTransport()
    monkey_sleep = lambda _s: None  # noqa: E731

    # The fake transport is active for BOTH phases — no network at all.
    original = runner.call_with_retry
    runner.call_with_retry = lambda payload, model, route, sleep: fake(
        payload, model, route, sleep
    )
    try:
        # First run: collect the first 4 samples only (simulated crash).
        for sample in plan[:4]:
            record, _ = runner.run_sample(sample, None, None, 1, {}, None, monkey_sleep)
            runner.append_record(runner.cell_path(out_dir, sample), record)
        before = fake.calls

        # Second run: the whole plan again.
        summary = runner.run_plan(plan, tmp_path, out_dir, {}, None, 1, monkey_sleep)
    finally:
        runner.call_with_retry = original

    # Only the 6 missing samples were actually collected.
    assert summary["skipped"] == 4
    assert fake.calls - before == 6
    # No duplicate idempotency keys anywhere on disk.
    keys = []
    for path in out_dir.glob("*.jsonl"):
        keys.extend(runner.read_idempotency_keys(path))
    assert len(keys) == 10
    assert len(set(keys)) == 10


def test_run_plan_writes_records_incrementally(tmp_path):
    import transport  # noqa: F401  (import check: module present)

    config = _config()
    names = ["p0"]
    plan = runner.build_plan(config, names, seed=1)[:1]
    original = runner.call_with_retry
    fake = FakeTransport()
    runner.call_with_retry = lambda payload, model, route, sleep: fake(
        payload, model, route, sleep
    )
    try:
        runner.run_plan(plan, tmp_path, tmp_path / "out", {}, None, 1)
    finally:
        runner.call_with_retry = original
    files = list((tmp_path / "out").glob("*.jsonl"))
    assert len(files) == 1
    records = [
        json.loads(line) for line in files[0].read_text(encoding="utf-8").splitlines()
    ]
    assert len(records) == 1
    assert records[0]["choice"] == 17
    assert records[0]["temperature"] == 1.0
    assert records[0]["cost_usd"] is None  # no prices configured
