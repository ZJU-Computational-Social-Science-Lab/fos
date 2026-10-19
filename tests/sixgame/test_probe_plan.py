"""Tests that the recognition-probe plan respects the CLI filters.

The runner must append the probe samples (60 for a DeepSeek-only
engineering run, 180 for all three models) to the decision plan, and
the --game/--variant/--arm/--model filters must shrink the probe part
of the plan exactly as they shrink the decision part.
"""

import runner


def _engineering_config():
    config = runner.default_config("engineering")
    config["models"] = ["deepseek-v4-flash"]
    return config


def test_deepseek_only_plan_yields_240_samples_with_60_probes():
    config = _engineering_config()
    names = [f"p{i}" for i in range(5)]
    decisions = runner.build_plan(config, names, seed=1)
    probes = runner.probe_plan(config, names, seed=1)
    assert len(decisions) == 180
    assert len(probes) == 60
    plan = decisions + probes
    assert len(plan) == 240
    assert all(s.namespace == "probes" for s in probes)
    assert all(s.model == "deepseek-v4-flash" for s in probes)


def test_all_model_plan_yields_720_samples():
    config = runner.default_config("engineering")
    names = [f"p{i}" for i in range(5)]
    plan = runner.build_plan(config, names, seed=1) + runner.probe_plan(
        config, names, seed=1
    )
    assert len(plan) == 720


def test_game_variant_arm_filters_restrict_probes():
    config = _engineering_config()
    names = [f"p{i}" for i in range(5)]
    # 2 rungs x 2 arms x 1 model x 5 personas = 20 probes for game 1120.
    by_game = runner.probe_plan(config, names, 1, game_filter="1120")
    assert len(by_game) == 20
    assert all(s.game == "1120" for s in by_game)
    # 1 rung x 2 arms x 5 personas = 10 probes for one variant.
    by_variant = runner.probe_plan(
        config, names, 1, game_filter="1120", variant_filter="r11-20"
    )
    assert len(by_variant) == 10
    assert all(s.variant == "r11-20" for s in by_variant)
    # 1 rung x 1 arm x 5 personas = 5 probes for one arm.
    by_arm = runner.probe_plan(
        config,
        names,
        1,
        game_filter="1120",
        variant_filter="r11-20",
        arm_filter="persona",
    )
    assert len(by_arm) == 5
    assert all(s.arm == "persona" for s in by_arm)
    # Model filter on its own shrinks the probe plan too.
    all_models = runner.default_config("engineering")
    by_model = runner.probe_plan(all_models, names, 1, model_filter="deepseek-v4-flash")
    assert len(by_model) == 60


def test_resume_keeps_only_60_probe_samples(tmp_path):
    import transport as t

    class FakeTransport:
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

    config = _engineering_config()
    names = [f"p{i}" for i in range(5)]
    decision_plan = runner.build_plan(config, names, seed=1)
    assert len(decision_plan) == 180
    full_plan = decision_plan + runner.probe_plan(config, names, seed=1)

    out_dir = tmp_path / "out"
    fake = FakeTransport()
    monkey_sleep = lambda _s: None  # noqa: E731
    original = runner.call_with_retry
    runner.call_with_retry = lambda payload, model, route, sleep: fake(
        payload, model, route, sleep
    )
    try:
        # Phase 1: all 180 decision samples already collected.
        runner.run_plan(decision_plan, tmp_path, out_dir, {}, None, 1, monkey_sleep)
        after_decisions = fake.calls
        # Phase 2: restart with the full (decisions + probes) plan.
        summary = runner.run_plan(full_plan, tmp_path, out_dir, {}, None, 1, monkey_sleep)
    finally:
        runner.call_with_retry = original

    assert after_decisions == 180
    assert summary["skipped"] == 180
    assert fake.calls - after_decisions == 60
    # Exactly the 60 probe samples were attempted.
    # No duplicates: every per-cell JSONL file holds unique keys, and
    # all 240 samples (180 decisions + 60 probes) are on disk exactly once.
    total = 0
    for path in out_dir.glob("*.jsonl"):
        keys = runner.read_idempotency_keys(path)
        assert len(keys) == len(set(keys)), f"duplicate keys in {path.name}"
        total += len(keys)
    assert total == 240
