"""This file tests the GAWorld scene orchestration behavior.

- test_type_identifier_matches_expected_value checks the scene type value.
- test_constructor_starts_with_empty_skipped_days checks skipped days starts empty.
- test_initialize_sets_subprocess_manager_and_translator checks initialize wires required collaborators.
- test_run_round_emits_one_event_per_translated_event checks run_round emits translated events.
- test_run_round_skips_day_when_translation_key_missing checks key errors skip a day without crashing.
- test_serialize_config_includes_skipped_days checks skipped days are returned in config serialization.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from fos.core.experiment.config import ExperimentConfig
from fos.core.experiment.scenes.gaworld.scene import GAWorldScene


def _make_config() -> ExperimentConfig:
    return ExperimentConfig(
        scenario_id="gaworld_scene",
        agents=[
            {"id": "1", "name": "Alice"},
            {"id": "2", "name": "Bob"},
        ],
        actions=[],
        parameters={"sim_days": 2, "agent_ids": ["1", "2"], "seed": 7},
    )


def test_type_identifier_matches_expected_value() -> None:
    assert GAWorldScene.TYPE == "gaworld_scene"


def test_constructor_starts_with_empty_skipped_days() -> None:
    scene = GAWorldScene(_make_config())
    assert scene.skipped_days == []


def test_initialize_sets_subprocess_manager_and_translator(monkeypatch) -> None:
    scene = GAWorldScene(_make_config())

    def _fake_launch() -> None:
        scene._subprocess_manager = SimpleNamespace(wait_for_day=lambda *args, **kwargs: {"last_day": 1})

    monkeypatch.setattr(scene, "_launch_subprocess", _fake_launch)

    scene.initialize(llm_client=object())

    assert scene._subprocess_manager is not None
    assert scene._translator is not None


def test_run_round_emits_one_event_per_translated_event(monkeypatch) -> None:
    scene = GAWorldScene(_make_config())

    def _fake_launch() -> None:
        scene._subprocess_manager = SimpleNamespace(wait_for_day=lambda *args, **kwargs: {"last_day": 1}, output_dir=Path("."))

    monkeypatch.setattr(scene, "_launch_subprocess", _fake_launch)
    monkeypatch.setattr(scene, "_read_day_data", lambda day_num: {"day": day_num, "agents": []})

    scene.initialize(llm_client=object())
    scene._translator = SimpleNamespace(
        translate_day=lambda _day_data: [{"agent": "Alice", "action": "work"}],
        translate_state_updates=lambda _day_data: {},
    )

    emitted: list[tuple[str, dict[str, Any]]] = []

    def _emit(event_type: str, payload: dict[str, Any]) -> None:
        emitted.append((event_type, payload))

    asyncio.run(scene.run_round(_emit))

    assert len(emitted) == 1
    assert emitted[0][0] == "experiment_action"


def test_run_round_skips_day_when_translation_key_missing(monkeypatch) -> None:
    scene = GAWorldScene(_make_config())

    def _fake_launch() -> None:
        scene._subprocess_manager = SimpleNamespace(wait_for_day=lambda *args, **kwargs: {"last_day": 1}, output_dir=Path("."))

    monkeypatch.setattr(scene, "_launch_subprocess", _fake_launch)
    monkeypatch.setattr(scene, "_read_day_data", lambda day_num: {"day": day_num, "agents": []})

    scene.initialize(llm_client=object())
    scene._translator = SimpleNamespace(
        translate_day=lambda _day_data: (_ for _ in ()).throw(KeyError("missing")),
        translate_state_updates=lambda _day_data: {},
    )

    emitted: list[tuple[str, dict[str, Any]]] = []

    asyncio.run(scene.run_round(lambda event_type, payload: emitted.append((event_type, payload))))

    assert scene.skipped_days == [1]
    assert emitted == []


def test_serialize_config_includes_skipped_days() -> None:
    scene = GAWorldScene(_make_config())
    scene.skipped_days.extend([1, 2])

    data = scene.serialize_config()

    assert "skipped_days" in data
    assert data["skipped_days"] == [1, 2]
