"""Regression tests for the three verification bugs found in RESULT-2723.

What this file checks, in plain language:

- The no-persona arm must never see the persona's written description,
  so its prompts cannot accidentally match the persona arm's prompts.
- Probe answers (free-text JSON) must be recorded with their parsed
  answer, a correct success flag, and a recognition coding.
- The analysis contrast and consistency tables must find cells even
  though cells are stored with the model in the key.
- Only gateway response caches are excluded from analysis; provider
  context/prompt-prefix caching is not an exclusion.
"""

from pathlib import Path

from analysis import (
    apply_exclusions,
    consistency_table,
    contrast_table,
)
from plan import Sample
from runner import (
    build_decision_prompt,
    persona_text_for,
    record_for,
)


def _sample(arm="persona", namespace="decisions", variant="basic", game="1120"):
    return Sample(
        game=game,
        variant=variant,
        arm=arm,
        model="deepseek-v4-flash",
        persona_id="alice",
        draw_id=0,
        role=None,
        namespace=namespace,
    )


# ------------------------------------------------------------------ #
# A1: no-persona arm never receives persona text
# ------------------------------------------------------------------ #


def test_no_persona_arm_gets_no_persona_text(tmp_path: Path):
    (tmp_path / "alice.txt").write_text("SECRET-PERSONA-BIO", encoding="utf-8")
    assert persona_text_for(_sample(arm="no_persona"), tmp_path) is None


def test_persona_arm_gets_persona_text(tmp_path: Path):
    (tmp_path / "alice.txt").write_text("SECRET-PERSONA-BIO", encoding="utf-8")
    assert persona_text_for(_sample(arm="persona"), tmp_path) == ("SECRET-PERSONA-BIO")


def test_no_persona_prompt_never_contains_persona_text():
    prompt = build_decision_prompt(_sample(arm="no_persona"), None, None, 0)
    assert "SECRET-PERSONA-BIO" not in prompt


def test_persona_arm_prompts_differ_by_persona():
    prompt_a = build_decision_prompt(_sample(arm="persona"), "BIO OF PERSON A", None, 0)
    prompt_b = build_decision_prompt(_sample(arm="persona"), "BIO OF PERSON B", None, 0)
    assert prompt_a != prompt_b


# ------------------------------------------------------------------ #
# A2: probe records carry the parsed answer and success flag
# ------------------------------------------------------------------ #


def _probe_response(content: str) -> dict:
    return {
        "model": "deepseek-v4-flash",
        "choices": [{"message": {"content": content}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5},
    }


def test_probe_record_choice_is_parsed_answer():
    body = _probe_response(
        '{"recognised": true, "answer": "This is the 11-20 game, '
        'people typically request 18."}'
    )
    record = record_for(
        _sample(namespace="probes", variant="r11-20"),
        "prompt",
        body,
        None,
        "direct",
        0.1,
        {},
    )
    assert record["choice"] == ("This is the 11-20 game, people typically request 18.")
    assert record["succeeded"] is True
    assert record["error"] is None


def test_probe_record_recognition_coding_is_stored():
    body = _probe_response(
        '{"recognised": true, "answer": "the arad rubinstein 11-20 game"}'
    )
    record = record_for(
        _sample(namespace="probes", variant="r11-20"),
        "prompt",
        body,
        None,
        "direct",
        0.1,
        {},
    )
    assert record["recognition"] == "RECOGNISING"


def test_probe_record_with_unparseable_body_fails():
    body = _probe_response("no json here at all")
    record = record_for(
        _sample(namespace="probes", variant="r11-20"),
        "prompt",
        body,
        None,
        "direct",
        0.1,
        {},
    )
    assert record["choice"] is None
    assert record["succeeded"] is False


# ------------------------------------------------------------------ #
# B1: contrast/consistency tables find cells keyed with the model
# ------------------------------------------------------------------ #


def _decision_record(persona_id, choice, variant, arm):
    return {
        "game": "1120",
        "variant": variant,
        "arm": arm,
        "model": "deepseek-v4-flash",
        "persona_id": persona_id,
        "draw_id": 0,
        "choice": choice,
        "succeeded": True,
        "cache_status": "MISS",
        "truncated": False,
        "error": None,
    }


def _cells():
    cells = {}
    for arm in ("persona", "no_persona"):
        cells[("1120", "basic", arm, "deepseek-v4-flash")] = [
            _decision_record(f"p{i}", 18, "basic", arm) for i in range(3)
        ]
        cells[("1120", "costless", arm, "deepseek-v4-flash")] = [
            _decision_record(f"p{i}", 20, "costless", arm) for i in range(3)
        ]
        cells[("1120", "r31-40", arm, "deepseek-v4-flash")] = [
            _decision_record(f"p{i}", 38, "r31-40", arm) for i in range(3)
        ]
    return cells


def test_contrast_table_rows_are_not_empty():
    rows = contrast_table(_cells(), boot=50, seed=0)
    filled = [r for r in rows if r["persona"] is not None]
    assert filled, "contrast table produced no filled rows"


def test_consistency_table_rows_are_not_empty():
    rows = consistency_table(_cells(), boot=50, seed=0)
    assert any(r["transformation"] == "1120_r31-40" for r in rows), (
        "consistency table produced no rows for 1120_r31-40"
    )


# ------------------------------------------------------------------ #
# C: only gateway response caches are excluded
# ------------------------------------------------------------------ #


def _usage_record(cache_status, cache_kind):
    return {
        "game": "1120",
        "variant": "basic",
        "arm": "persona",
        "model": "deepseek-v4-flash",
        "persona_id": "p",
        "draw_id": 0,
        "choice": 18,
        "succeeded": True,
        "cache_status": cache_status,
        "cache_kind": cache_kind,
        "truncated": False,
        "error": None,
    }


def test_context_cache_records_are_kept():
    kept, counts = apply_exclusions([_usage_record("HIT", "context")])
    assert kept and "cache_hit" not in counts


def test_response_cache_records_are_excluded():
    kept, counts = apply_exclusions([_usage_record("HIT", "response")])
    assert not kept and counts.get("cache_hit") == 1


def test_runner_classifies_prompt_prefix_hits_as_context_cache():
    body = _probe_response('{"recognised": false, "answer": ""}')
    body["usage"]["prompt_cache_hit_tokens"] = 8
    record = record_for(
        _sample(namespace="probes", variant="r11-20"),
        "prompt",
        body,
        None,
        "direct",
        0.1,
        {},
    )
    assert record["cache_status"] == "HIT"
    assert record["cache_kind"] == "context"
