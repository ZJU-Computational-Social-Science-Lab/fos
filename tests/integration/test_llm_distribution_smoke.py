"""
Smoke test for LLM distribution at runtime.

Verifies that when simulation runs, different agents use different LLM clients.
This test should FAIL with current implementation.
"""
import pytest
from unittest.mock import MagicMock, patch, call
from fos.core.llm.client import LLMClient
from fos.core.llm_config import LLMConfig
from fos.core.experiment.scene import ExperimentScene
from fos.core.experiment.config import ExperimentConfig
from fos.core.experiment.game_configs import GameConfig
from fos.core.experiment.information_model import InformationModel


@pytest.mark.xfail(reason="mock dialect returns XML-format responses incompatible with JSON action parser — needs source-level fix")
@pytest.mark.asyncio
async def test_llm_distribution_runtime():
    """Smoke test that verifies runtime LLM distribution.

    This test verifies that when running a simulation:
    1. Agents with different llm_config.dialect values
    2. Should use different LLM clients
    3. Currently, they all share the same default client (BUG)
    """
    # Create scene using mock dialect so no real API calls are made
    scene = ExperimentScene(
        ExperimentConfig(
            scenario_id="test",
            agents=[
                {"name": "Agent1", "properties": {"provider_id": 1}, "llm_config": {"dialect": "mock"}},
                {"name": "Agent2", "properties": {"provider_id": 2}, "llm_config": {"dialect": "mock"}},
            ],
            actions=[
                {"name": "cooperate", "description": "Cooperate action"},
                {"name": "defect", "description": "Defect action"},
            ],
        )
    )

    mock_client = LLMClient(LLMConfig(dialect="mock"))

    # Initialize scene with default client
    scene.initialize(mock_client)

    # Try to run one round
    result = await scene.run_round(lambda event_type, data: None)

    # Verify round completed
    assert result is not None
    assert result.round_num == 1

    assert len(result.actions) == 2

    # Verify that both agents made decisions
    for action_result in result.actions:
        assert action_result.success
        assert action_result.action_name in ["cooperate", "defect"]


@pytest.mark.xfail(reason="per-agent LLM client creation not yet implemented — tests a known bug, out of scope")
@pytest.mark.asyncio
async def test_llm_client_selection():
    """Test that ExperimentRunner selects different LLM clients for different agents.

    This test patches LLMClient creation to verify that different
    providers create different clients.
    """
    # Track which clients are created
    created_clients = []

    def mock_llm_client_init(self, *args, **kwargs):
        """Mock LLMClient __init__ to track creations."""
        # Extract dialect from kwargs
        dialect = kwargs.get('dialect', 'unknown')
        client = MagicMock()
        client.dialect = dialect
        client.chat = MagicMock(return_value='{"action": "cooperate"}')
        created_clients.append(client)
        return client

    # Patch LLMClient.__init__
    with patch('fos.core.llm.client.LLMClient.__init__', mock_llm_client_init):
        # Create scene with different providers
        scene = ExperimentScene(
            ExperimentConfig(
                scenario_id="test",
                agents=[
                    {"name": "Agent1", "properties": {}, "llm_config": {"dialect": "openai", "model": "gpt-4o"}},
                    {"name": "Agent2", "properties": {}, "llm_config": {"dialect": "ollama", "model": "llama3"}},
                ],
                actions=[
                    {"name": "cooperate", "description": "Cooperate action"},
                    {"name": "defect", "description": "Defect action"},
                ],
            )
        )

        # Create mock client
        mock_client = MagicMock(spec=LLMClient)
        mock_client.chat = MagicMock(return_value='{"action": "cooperate"}')

        # Initialize scene
        scene.initialize(mock_client)

        # BUG VERIFICATION:
        # With current implementation, only one client is created (the default)
        # The fix should create per-agent clients
        # This test should FAIL until the bug is fixed
        assert len(created_clients) >= 2, f"Expected 2+ LLM clients to be created, got {len(created_clients)}"
