"""Tests for answer parsing and truncation detection.

Parsing must accept the exact JSON the prompt asks for, reject anything
that is not a legal action (without crashing), and truncation must be
detected from the finish reason and excluded downstream.
"""

import runner


def test_parses_valid_amount_and_reason():
    choice, reason = runner.parse_answer(
        '{"reason": "I want a middle anchor.", "amount": 17}',
        "amount",
        tuple(range(11, 21)),
    )
    assert choice == 17
    assert reason == "I want a middle anchor."


def test_parses_json_wrapped_in_prose():
    choice, _ = runner.parse_answer(
        'Sure! Here is my answer: {"reason": "x", "amount": 20} Thanks',
        "amount",
        tuple(range(11, 21)),
    )
    assert choice == 20


def test_rejects_choice_outside_legal_set():
    choice, _ = runner.parse_answer(
        '{"reason": "", "amount": 25}', "amount", tuple(range(11, 21))
    )
    assert choice is None


def test_rejects_missing_or_malformed_json():
    assert runner.parse_answer(None, "amount", (1, 2))[0] is None
    assert runner.parse_answer("no json at all", "amount", (1, 2))[0] is None
    assert runner.parse_answer("{broken", "amount", (1, 2))[0] is None
    assert runner.parse_answer('{"amount": "high"}', "amount", (1, 2))[0] is None


def test_parses_die_report():
    choice, _ = runner.parse_answer(
        '{"reason": "honest", "report": 4}', "report", (1, 2, 3, 4, 5, 6)
    )
    assert choice == 4


def test_parses_action_case_insensitively():
    choice, _ = runner.parse_answer(
        '{"reason": "r", "action": "j"}', "action", games_actions()
    )
    assert choice == "J"


def games_actions():
    from games import PMS_ACTIONS

    return PMS_ACTIONS


def test_truncation_detection_by_finish_reason():
    assert runner.truncated("length") is True
    assert runner.truncated("incomplete") is True
    assert runner.truncated("MAX_TOKENS") is True
    assert runner.truncated("stop") is False
    assert runner.truncated(None) is False


def test_truncated_response_is_marked_and_fails():
    sample = runner.Sample(
        "1120", "basic", "persona", "deepseek-v4-flash", "alice", 0, None, "decisions"
    )
    prompt = runner.build_decision_prompt(sample, None, None, 0)
    response = {
        "choices": [
            {
                "message": {"content": '{"reason": "r", "amount": 17}'},
                "finish_reason": "length",
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 32768},
        "model": "deepseek-v4-flash",
    }
    record = runner.record_for(sample, prompt, response, None, "direct", 1.0, {})
    assert record["truncated"] is True
    assert record["succeeded"] is False


def test_truncated_records_excluded_in_analysis():
    records = [
        {
            "game": "1120",
            "variant": "basic",
            "arm": "persona",
            "model": "m",
            "persona_id": "a",
            "draw_id": 0,
            "choice": 17,
            "truncated": True,
            "finish_reason": "length",
            "cache_status": "MISS",
            "error": None,
            "succeeded": True,
        },
        {
            "game": "1120",
            "variant": "basic",
            "arm": "persona",
            "model": "m",
            "persona_id": "a",
            "draw_id": 1,
            "choice": 19,
            "truncated": False,
            "finish_reason": "stop",
            "cache_status": "MISS",
            "error": None,
            "succeeded": True,
        },
    ]
    kept, counts = __import__("analysis").apply_exclusions(records)
    assert len(kept) == 1 and kept[0]["choice"] == 19
    assert counts["truncated"] == 1
