"""Integration checks for GAWorld registry and runtime wiring.

This file checks that GAWorld is connected through exports, registries, and runtime routing.
Each test verifies one user-visible wiring expectation for the GAWorld scene.
"""

from __future__ import annotations

import pytest

from fos.backend.services import simtree_runtime
from fos.core.experiment.scenes.gaworld import GAWorldScene
from fos.core.registry import get_information_model, get_scene_class
from fos.core.scenarios.registry import ALL_SCENARIOS


def test_gaworld_scene_is_importable_from_package() -> None:
    """GAWorldScene can be imported from the gaworld package export."""
    assert GAWorldScene is not None


def test_registry_returns_gaworld_scene_class() -> None:
    """Scene registry returns the GAWorldScene class for gaworld_scene."""
    assert get_scene_class("gaworld_scene") is GAWorldScene


def test_gaworld_scenario_exists_with_expected_category() -> None:
    """Scenario registry includes gaworld in generative_city category."""
    scenario = next((item for item in ALL_SCENARIOS if item.get("id") == "gaworld"), None)
    assert scenario is not None
    assert scenario["category"] == "generative_city"


def test_gaworld_scenario_does_not_include_gaworld_path_parameter() -> None:
    """GAWorld scenario parameters do not expose gaworld_path to clients."""
    scenario = next(item for item in ALL_SCENARIOS if item.get("id") == "gaworld")
    parameter_ids = {param.get("id") for param in scenario.get("parameters", [])}
    assert "gaworld_path" not in parameter_ids


def test_information_model_for_gaworld_scene_is_all_without_scores() -> None:
    """GAWorld info model uses global scope and hides scores."""
    model = get_information_model("gaworld_scene")
    assert model.scope_type == "all"
    assert model.include_scores is False


def test_simtree_routing_raises_when_gaworld_path_is_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Routing to gaworld_scene fails with i18n key when env path is missing."""
    monkeypatch.delenv("GAWORLD_PATH", raising=False)

    sim_record = type(
        "SimRecord",
        (),
        {
            "id": "SIM-GAWORLD-1",
            "scene_type": "gaworld_scene",
            "scene_config": {"parameters": {}},
            "name": "GAWorld Integration Test",
            "description": "",
            "notes": "",
            "agent_config": {"agents": []},
        },
    )()

    with pytest.raises(ValueError, match="gaworld.error.path_not_set"):
        simtree_runtime._build_tree_for_sim(sim_record, clients={})
