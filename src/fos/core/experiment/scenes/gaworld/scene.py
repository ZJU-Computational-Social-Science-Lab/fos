"""This file runs a GAWorld-backed experiment scene.

- GAWorldScene stores GAWorld-specific config values and run state.
- initialize sets up mapping, translator, and subprocess launch.
- _launch_subprocess prepares GAWorld input files and starts run managers.
- run_round waits for one day, translates actions, updates state, and returns result.
- _read_day_data loads one day of per-agent action and state files.
- serialize_config adds GAWorld extra fields to base serialized scene data.
- is_complete reports when configured simulation days are done.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any, Callable

from fos.core.experiment.runner import RoundResult
from fos.core.experiment.scene import ExperimentScene
from fos.core.experiment.scenes.gaworld.profiles import export_profiles_csv, load_profiles
from fos.core.experiment.scenes.gaworld.subprocess_manager import GAWorldSubprocessManager
from fos.core.experiment.scenes.gaworld.translator import GAWorldOutputTranslator


class GAWorldScene(ExperimentScene):
    """ExperimentScene implementation that reads actions from GAWorld outputs."""

    TYPE = "gaworld_scene"

    def __init__(self, config) -> None:
        super().__init__(config)
        params = config.parameters or {}
        self.skipped_days: list[int] = []
        self._sim_days: int = int(params.get("sim_days", 0) or 0)
        self._agent_ids: list[str] = list(params.get("agent_ids", []))
        self._seed: int = int(params.get("seed", 0) or 0)
        self._translator: GAWorldOutputTranslator | None = None
        self._subprocess_manager: GAWorldSubprocessManager | None = None
        self._comparative_managers: tuple[GAWorldSubprocessManager, GAWorldSubprocessManager] | None = None

    def initialize(self, llm_client, provider_clients: dict | None = None) -> None:
        # llm_client is intentionally unused because GAWorld manages its own LLM calls.
        self.llm_client = llm_client
        self._agent_name_map = {
            int(agent.get("id", 0)): str(agent.get("name", agent.get("id", "")))
            for agent in self.config.agents
        }
        self._translator = GAWorldOutputTranslator(self._agent_name_map)
        self._launch_subprocess()

    def _launch_subprocess(self) -> None:
        profiles = load_profiles()
        if self._agent_ids:
            selected = set(self._agent_ids)
            profiles = [profile for profile in profiles if profile.id in selected]

        temp_dir = Path(tempfile.mkdtemp(prefix="gaworld_"))
        export_profiles_csv(profiles, temp_dir / "profiles.csv")

        config_overrides: dict[str, Any] = {
            "sim_days": self._sim_days,
            "seed": self._seed,
            "agent_ids": self._agent_ids,
            "profiles_csv": str(temp_dir / "profiles.csv"),
        }

        gaworld_path = Path(self.config.parameters.get("gaworld_path", "."))
        output_dir = Path(self.config.parameters.get("output_dir", temp_dir / "output"))

        if bool(self.config.parameters.get("intervention_enabled", False)):
            event_config = dict(self.config.parameters.get("event_config", {}))
            self._comparative_managers = GAWorldSubprocessManager.launch_comparative(
                gaworld_path=gaworld_path,
                event_config=event_config,
                base_output_dir=output_dir,
                config_overrides=config_overrides,
            )
            self._subprocess_manager = self._comparative_managers[1]
            return

        manager = GAWorldSubprocessManager(
            gaworld_path=gaworld_path,
            config_overrides=config_overrides,
            output_dir=output_dir,
            preserve_output=True,
        )
        manager.launch()
        self._subprocess_manager = manager

    async def run_round(self, event_emitter: Callable[[str, dict], None]) -> RoundResult:
        self.current_round += 1
        day_num = self.current_round
        if self._subprocess_manager is None or self._translator is None:
            raise RuntimeError("gaworld.error.not_initialized")

        self._subprocess_manager.wait_for_day(day_num, timeout=300)
        day_data = self._read_day_data(day_num)

        try:
            events = self._translator.translate_day(day_data)
            state_updates = self._translator.translate_state_updates(day_data)
        except (json.JSONDecodeError, KeyError):
            self.skipped_days.append(day_num)
            return RoundResult(round_num=day_num, actions=[], completed=True)

        for event in events:
            event_emitter("experiment_action", event)

        for agent_name, updates in state_updates.items():
            if agent_name in self.state.agents:
                self.state.agents[agent_name].properties.update(updates)

        return RoundResult(round_num=day_num, actions=[], completed=True)

    def _read_day_data(self, day_num: int) -> dict[str, Any]:
        if self._subprocess_manager is None:
            raise RuntimeError("gaworld.error.not_initialized")

        memory_dir = self._subprocess_manager.output_dir / "memory"
        agents: dict[str, dict[str, Any]] = {}
        for agent_id in self._agent_ids:
            actions_path = memory_dir / f"agent_{agent_id}_actions.json"
            state_path = memory_dir / f"agent_{agent_id}.json"
            actions = json.loads(actions_path.read_text(encoding="utf-8")) if actions_path.exists() else []
            state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
            agents[agent_id] = {"actions": actions, "state": state}

        return {"day": day_num, "agents": agents}

    def serialize_config(self) -> dict:
        data = super().serialize_config()
        data["skipped_days"] = list(self.skipped_days)
        return data

    def is_complete(self) -> bool:
        return self.current_round >= self._sim_days
