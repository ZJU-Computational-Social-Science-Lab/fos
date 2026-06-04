"""These tests check the real council startup path and the discussion startup path.

This file makes sure the backend can build the right scene for each scenario.
The helper builds a fake saved simulation record.
The first test checks council chamber uses the council scene and keeps working.
The second test checks open discussion still uses the normal experiment scene.
"""

from types import SimpleNamespace

from fos.backend.services import simtree_runtime
from fos.core.experiment.config import ExperimentConfig
from fos.core.experiment.scene import ExperimentScene
from fos.core.experiment.scenes.council_experiment import (
    CouncilCyclePhase,
    CouncilExperimentScene,
)


def _make_sim_record(scenario_id: str) -> SimpleNamespace:
    """Build a small fake simulation record for runtime tree tests."""
    return SimpleNamespace(
        id=f"{scenario_id}-sim",
        scene_type="experiment_template",
        name=scenario_id,
        description="test simulation",
        notes="",
        latest_state=None,
        scene_config={
            "generic_config": {
                "scenario_id": scenario_id,
                "description": "Talk about a budget proposal.",
                "parameters": {
                    "proposal_text": "Build a new library.",
                    "deliberation_rounds": 2,
                    "voting_threshold": 0.5,
                    "topic": "What should the group do?",
                },
                "social_network": {"edges": []},
                "locale": "en",
            }
        },
        agent_config={
            "agents": [
                {"name": "Alice", "role_prompt": "You are Alice."},
                {"name": "Bob", "role_prompt": "You are Bob."},
                {"name": "Cara", "role_prompt": "You are Cara."},
            ]
        },
    )


def _make_council_scene() -> CouncilExperimentScene:
    """Build a small council scene directly for focused phase tests."""
    return CouncilExperimentScene(
        ExperimentConfig(
            scenario_id="council",
            agents=[
                {"name": "Alice", "role_prompt": "You are Alice."},
                {"name": "Bob", "role_prompt": "You are Bob."},
            ],
            actions=[],
            parameters={
                "proposal_text": "Build a new library.",
                "deliberation_rounds": 2,
                "voting_threshold": 0.5,
            },
            description="Council test",
            locale="en",
        )
    )


def test_council_chamber_runtime_builds_the_council_scene() -> None:
    """Council chamber should build the council scene through runtime startup."""
    tree = simtree_runtime._build_tree_for_sim(_make_sim_record("council_chamber"), clients={})

    scene = tree.nodes[tree.root]["sim"].scene

    assert isinstance(scene, CouncilExperimentScene)
    assert scene.get_scene_actions("Alice") == ["speak", "skip"]
    assert "Current Phase" in scene.get_agent_status_prompt("Alice")


def test_council_scene_switches_actions_when_voting_starts() -> None:
    """Council scene should show vote actions during the voting phase."""
    scene = _make_council_scene()

    assert scene.get_scene_actions("Alice") == ["speak", "skip"]

    scene.cycle_phase = CouncilCyclePhase.VOTING

    assert scene.get_scene_actions("Alice") == ["vote_yes", "vote_no", "abstain"]
    assert "Current Phase: voting" in scene.get_agent_status_prompt("Alice")


def test_open_discussion_runtime_builds_the_normal_scene() -> None:
    """Open discussion should still build the normal experiment scene."""
    tree = simtree_runtime._build_tree_for_sim(_make_sim_record("open_discussion"), clients={})

    scene = tree.nodes[tree.root]["sim"].scene

    assert isinstance(scene, ExperimentScene)
    assert not isinstance(scene, CouncilExperimentScene)
