"""This file tests the GAWorld scene orchestration behavior.

- test_type_identifier_matches_expected_value checks the scene type value.
- test_constructor_starts_with_empty_skipped_days checks skipped days starts empty.
- test_initialize_sets_translator_without_starting_subprocess checks initialize avoids starting GAWorld.
- test_run_round_launches_subprocess_on_first_round checks first run_round lazily starts GAWorld.
- test_run_round_emits_one_event_per_translated_event checks run_round emits translated events.
- test_run_round_skips_day_when_translation_key_missing checks key errors skip a day without crashing.
- test_launch_subprocess_passes_gaworld_output_paths checks GAWorld writes under the FOS output folder.
- test_serialize_config_includes_skipped_days checks skipped days are returned in config serialization.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import fos.core.experiment.scenes.gaworld.scene as scene_module
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


def test_initialize_sets_translator_without_starting_subprocess(monkeypatch) -> None:
    scene = GAWorldScene(_make_config())
    launch_calls: list[str] = []

    def _fake_launch() -> None:
        launch_calls.append("called")
        scene._subprocess_manager = SimpleNamespace(wait_for_day=lambda *args, **kwargs: {"last_day": 1})

    monkeypatch.setattr(scene, "_launch_subprocess", _fake_launch)

    scene.initialize(llm_client=object())

    assert launch_calls == []
    assert scene._subprocess_manager is None
    assert scene._translator is not None


def test_run_round_launches_subprocess_on_first_round(monkeypatch) -> None:
    scene = GAWorldScene(_make_config())
    launch_calls: list[str] = []

    def _fake_launch() -> None:
        launch_calls.append("called")
        scene._subprocess_manager = SimpleNamespace(wait_for_day=lambda *args, **kwargs: {"last_day": 1}, output_dir=Path("."))

    monkeypatch.setattr(scene, "_launch_subprocess", _fake_launch)
    monkeypatch.setattr(scene, "_read_day_data", lambda day_num: {"day": day_num, "agents": []})

    scene.initialize(llm_client=object())
    scene._translator = SimpleNamespace(
        translate_day=lambda _day_data: [],
        translate_state_updates=lambda _day_data: {},
    )

    asyncio.run(scene.run_round(lambda _event_type, _payload: None))

    assert launch_calls == ["called"]


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


def test_launch_subprocess_passes_gaworld_output_paths(tmp_path: Path, monkeypatch) -> None:
    output_dir = tmp_path / "gaworld-output"
    config = _make_config()
    config.parameters["output_dir"] = output_dir
    config.parameters["gaworld_path"] = tmp_path / "GAWorld"
    captured: dict[str, Any] = {}

    class FakeManager:
        def __init__(self, **kwargs: Any) -> None:
            captured.update(kwargs)
            self.output_dir = kwargs["output_dir"]

        def launch(self) -> None:
            captured["launched"] = True

    monkeypatch.setattr(scene_module, "load_profiles", lambda: [])
    monkeypatch.setattr(scene_module, "export_profiles_csv", lambda _profiles, _path: None)
    monkeypatch.setattr(scene_module, "GAWorldSubprocessManager", FakeManager)

    scene = GAWorldScene(config)
    scene._launch_subprocess()

    overrides = captured["config_overrides"]
    assert overrides["memory_dir"] == str(output_dir / "memory")
    assert overrides["log_dir"] == str(output_dir / "logs")
    assert overrides["diary_output_dir"] == str(output_dir / "diaries")
    assert overrides["environment_output_dir"] == str(output_dir / "environment")
    assert overrides["state_output_dir"] == str(output_dir / "state")
    assert overrides["network_output_dir"] == str(output_dir / "network")
    assert overrides["vector_db_path"] == str(output_dir / "memory" / "vector_db.sqlite")
    assert overrides["visualization"]["output_dir"] == str(output_dir / "visualization")
    assert overrides["intervention"]["output_dir"] == str(output_dir / "intervention")
    assert captured["output_dir"] == output_dir
    assert captured["launched"] is True


def test_serialize_config_includes_skipped_days() -> None:
    scene = GAWorldScene(_make_config())
    scene.skipped_days.extend([1, 2])

    data = scene.serialize_config()

    assert "skipped_days" in data
    assert data["skipped_days"] == [1, 2]
