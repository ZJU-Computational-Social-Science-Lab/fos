"""This file runs a GAWorld-backed experiment scene.

- GAWorldScene stores GAWorld-specific config values and run state.
- initialize sets up mapping and translator without starting subprocesses.
- _agent_id_from_config reads one agent ID from config.
- _agent_file_ids chooses the GAWorld agent output files to read.
- _launch_subprocess prepares GAWorld input files and starts run managers.
- _build_llm_env_overrides passes only GAWorld-specific LLM keys to GAWorld.
- _build_output_overrides tells GAWorld where to save every output file.
- run_round waits for one day, translates actions, updates state, and returns result.
- _read_day_data loads one day of per-agent action and state files.
- serialize_config adds GAWorld extra fields to base serialized scene data.
- is_complete reports when configured simulation days are done.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from fos.core.experiment.runner import RoundResult
from fos.core.experiment.scene import ExperimentScene
from fos.core.experiment.scenes.gaworld.profiles import export_profiles_csv, load_profiles
from fos.core.experiment.scenes.gaworld.subprocess_manager import GAWorldSubprocessManager
from fos.core.experiment.scenes.gaworld.translator import GAWorldOutputTranslator

logger = logging.getLogger(__name__)

GAWORLD_LLM_ENV_KEYS = ("MINIMAX_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_API_KEY")
GAWORLD_DEDICATED_LLM_ENV_KEY = "GAWORLD_LLM_API_KEY"
FOS_OLLAMA_PROVIDER_NAME = "fos_ollama"


@dataclass(frozen=True)
class OllamaProviderSettings:
    """Stores the Ollama endpoint GAWorld needs."""

    base_url: str
    model: str
    timeout: int = 600


def _build_output_overrides(output_dir: Path) -> dict[str, Any]:
    """Builds GAWorld settings so all saved files go under one FOS folder."""
    memory_dir = output_dir / "memory"
    return {
        "memory_dir": str(memory_dir),
        "log_dir": str(output_dir / "logs"),
        "diary_output_dir": str(output_dir / "diaries"),
        "environment_output_dir": str(output_dir / "environment"),
        "state_output_dir": str(output_dir / "state"),
        "network_output_dir": str(output_dir / "network"),
        "vector_db_path": str(memory_dir / "vector_db.sqlite"),
        "intervention": {
            "output_dir": str(output_dir / "intervention"),
        },
        "visualization": {
            "output_dir": str(output_dir / "visualization"),
        },
    }


def _has_gaworld_llm_env_key() -> bool:
    """Returns True when the current process already has a GAWorld LLM key."""
    return any(bool(os.environ.get(key)) for key in GAWORLD_LLM_ENV_KEYS)


def _ollama_generate_url(base_url: str) -> str:
    """Converts an Ollama server URL into GAWorld's generate endpoint URL."""
    clean_url = str(base_url or "").strip().rstrip("/")
    if not clean_url:
        clean_url = "http://localhost:11434"
    if clean_url.endswith("/api/generate"):
        return clean_url
    if clean_url.endswith("/api"):
        return f"{clean_url}/generate"
    return f"{clean_url}/api/generate"


def _ollama_settings_from_client(client: Any) -> OllamaProviderSettings | None:
    """Reads Ollama settings from a FOS LLMClient-like object."""
    provider = getattr(client, "provider", None)
    if provider is None:
        return None
    dialect = str(getattr(provider, "dialect", "") or "").lower()
    if dialect != "ollama":
        return None
    model = str(getattr(provider, "model", "") or "").strip()
    if not model:
        return None
    base_url = str(getattr(provider, "base_url", "") or "").strip() or "http://localhost:11434"
    timeout = int(float(getattr(client, "timeout_s", 600) or 600))
    return OllamaProviderSettings(base_url=base_url, model=model, timeout=timeout)


def _ollama_settings_from_env() -> OllamaProviderSettings | None:
    """Reads Ollama settings from FOS environment variables."""
    dialect = os.environ.get("LLM_DIALECT", "").strip().lower()
    model = os.environ.get("LLM_MODEL", "").strip()
    if dialect != "ollama" or not model:
        return None
    base_url = os.environ.get("LLM_BASE_URL", "").strip() or os.environ.get("OLLAMA_BASE_URL", "").strip()
    return OllamaProviderSettings(base_url=base_url or "http://localhost:11434", model=model)


def _build_ollama_config_overrides(settings: OllamaProviderSettings) -> dict[str, Any]:
    """Builds GAWorld config overrides for the resolved Ollama provider."""
    return {
        "llm": {
            "providers": {
                FOS_OLLAMA_PROVIDER_NAME: {
                    "type": "ollama",
                    "url": _ollama_generate_url(settings.base_url),
                    "model": settings.model,
                    "timeout": settings.timeout,
                },
            },
            "routing": {
                "default": FOS_OLLAMA_PROVIDER_NAME,
                "tasks": {
                    "schedule": FOS_OLLAMA_PROVIDER_NAME,
                },
            },
        },
    }


class GAWorldScene(ExperimentScene):
    """ExperimentScene implementation that reads actions from GAWorld outputs."""

    TYPE = "gaworld_scene"

    def __init__(self, config) -> None:
        super().__init__(config)
        params = config.parameters or {}
        self.skipped_days: list[int] = []
        self._sim_days: int = int(params.get("sim_days", 0) or 0)
        raw_agent_ids = params.get("agent_ids", [])
        if isinstance(raw_agent_ids, str):
            self._agent_ids = [part.strip() for part in raw_agent_ids.split(",") if part.strip()]
        else:
            self._agent_ids = [str(agent_id) for agent_id in raw_agent_ids if str(agent_id).strip()]
        self._seed: int = int(params.get("seed", 0) or 0)
        self._translator: GAWorldOutputTranslator | None = None
        self._subprocess_manager: GAWorldSubprocessManager | None = None
        self._comparative_managers: tuple[GAWorldSubprocessManager, GAWorldSubprocessManager] | None = None
        self._provider_clients: dict = {}
        self._agent_name_map: dict[int, str] = {}

    def initialize(self, llm_client, provider_clients: dict | None = None) -> None:
        self.llm_client = llm_client
        self._provider_clients = provider_clients or {}
        self._agent_name_map = {}
        for agent in self.config.agents:
            agent_id = self._agent_id_from_config(agent)
            if agent_id is None:
                continue
            self._agent_name_map[agent_id] = str(agent.get("name", agent_id))
        self._translator = GAWorldOutputTranslator(self._agent_name_map)
        super().initialize(llm_client, provider_clients=provider_clients)
        # Subprocess is launched lazily on first run_round() call.

    def _agent_id_from_config(self, agent: dict[str, Any]) -> int | None:
        """Reads one numeric GAWorld agent ID from config."""
        raw_agent_id = agent.get("id")
        if raw_agent_id is None:
            return None
        try:
            return int(str(raw_agent_id).strip())
        except ValueError:
            logger.warning("gaworld.warning.invalid_agent_id", extra={"agent_id": raw_agent_id})
            return None

    def _agent_file_ids(self, memory_dir: Path) -> list[int]:
        """Chooses agent IDs from config, or scans memory files as a fallback."""
        if self._agent_name_map:
            return list(self._agent_name_map.keys())

        file_ids: list[int] = []
        for actions_path in memory_dir.glob("agent_*_actions.json"):
            raw_agent_id = actions_path.name.removeprefix("agent_").removesuffix("_actions.json")
            try:
                file_ids.append(int(raw_agent_id))
            except ValueError:
                logger.warning("gaworld.warning.invalid_agent_file", extra={"path": str(actions_path)})
        return sorted(file_ids)

    def _resolve_ollama_settings(self) -> OllamaProviderSettings | None:
        """Finds the Ollama settings FOS is already using."""
        settings = _ollama_settings_from_client(getattr(self, "llm_client", None))
        if settings is not None:
            return settings

        for client in self._provider_clients.values():
            settings = _ollama_settings_from_client(client)
            if settings is not None:
                return settings

        return _ollama_settings_from_env()

    def _build_llm_env_overrides(self) -> dict[str, str]:
        """Builds subprocess LLM env vars from GAWorld-specific environment only."""
        dedicated_api_key = os.environ.get(GAWORLD_DEDICATED_LLM_ENV_KEY)
        has_existing_gaworld_key = _has_gaworld_llm_env_key()

        if dedicated_api_key:
            logger.info("GAWorld injecting GAWORLD_LLM_API_KEY as MINIMAX_API_KEY.")
            return {"MINIMAX_API_KEY": dedicated_api_key}
        if has_existing_gaworld_key:
            logger.info("GAWorld LLM API key already present in parent environment; inheriting it.")
            return {}

        logger.warning("gaworld.warning.no_llm_key")
        return {}

    def _launch_subprocess(self) -> None:
        profiles = load_profiles()
        if self._agent_ids:
            selected = set(self._agent_ids)
            profiles = [profile for profile in profiles if profile.id in selected]

        temp_dir = Path(tempfile.mkdtemp(prefix="gaworld_"))
        output_dir = Path(self.config.parameters.get("output_dir", temp_dir / "output"))
        config_overrides: dict[str, Any] = {
            "sim_days": self._sim_days,
            "seed": self._seed,
            **_build_output_overrides(output_dir),
        }
        if profiles:
            profiles_path = temp_dir / "profiles.csv"
            export_profiles_csv(profiles, profiles_path)
            config_overrides["csv_path"] = str(profiles_path)
        if self._agent_ids:
            config_overrides["agent_ids"] = self._agent_ids
        ollama_settings = self._resolve_ollama_settings()
        if ollama_settings is not None:
            config_overrides.update(_build_ollama_config_overrides(ollama_settings))
            env_overrides = {}
        else:
            env_overrides = self._build_llm_env_overrides()

        gaworld_path_str = (
            self.config.parameters.get("gaworld_path")
            or os.environ.get("GAWORLD_PATH")
            or "."
        )
        gaworld_path = Path(gaworld_path_str)
        logger.info(
            "GAWorld _launch_subprocess: gaworld_path=%s (from_param=%s, from_env=%s)",
            gaworld_path,
            self.config.parameters.get("gaworld_path"),
            os.environ.get("GAWORLD_PATH"),
        )

        if bool(self.config.parameters.get("intervention_enabled", False)):
            event_config = dict(self.config.parameters.get("event_config", {}))
            self._comparative_managers = GAWorldSubprocessManager.launch_comparative(
                gaworld_path=gaworld_path,
                event_config=event_config,
                base_output_dir=output_dir,
                config_overrides=config_overrides,
                env_overrides=env_overrides,
            )
            self._subprocess_manager = self._comparative_managers[1]
            return

        manager = GAWorldSubprocessManager(
            gaworld_path=gaworld_path,
            config_overrides=config_overrides,
            output_dir=output_dir,
            preserve_output=True,
            env_overrides=env_overrides,
        )
        manager.launch()
        self._subprocess_manager = manager

    async def run_round(self, event_emitter: Callable[[str, dict], None]) -> RoundResult:
        self.current_round += 1
        day_num = self.current_round
        if self._subprocess_manager is None:
            self._launch_subprocess()
            logger.info(f"GAWorld subprocess launched for day {self.current_round}")
            if self._subprocess_manager is not None:
                output_dir = self._subprocess_manager.output_dir
                logger.info(f"GAWorld output_dir: {output_dir}")
                logger.info(f"GAWorld output_dir exists: {output_dir.exists()}")
                if output_dir.exists():
                    for root, _, files in os.walk(output_dir):
                        for file_name in files:
                            logger.info(f"GAWorld output file: {os.path.join(root, file_name)}")
        if self._subprocess_manager is None or self._translator is None:
            raise RuntimeError("gaworld.error.not_initialized")

        sim_state = self._subprocess_manager.wait_for_day(day_num, timeout=300)
        logger.info(f"GAWorld day {day_num} sim_state: {sim_state}")
        day_data = self._read_day_data(day_num)
        logger.info(f"GAWorld day {day_num} agents_data: {day_data}")

        try:
            events = self._translator.translate_day(day_data)
            logger.info(f"GAWorld day {day_num} translated {len(events)} events")
            if not events:
                agents_in_data = day_data.get("agents", [])
                logger.warning(
                    "GAWorld day %d produced 0 events — agents_in_data=%d, "
                    "agent_name_map=%s, day_data_keys=%s",
                    day_num, len(agents_in_data),
                    list(self._agent_name_map.keys())[:5],
                    list(day_data.keys()),
                )
            state_updates = self._translator.translate_state_updates(day_data)
        except (json.JSONDecodeError, KeyError):
            logger.exception("GAWorld day %d translation failed — skipping", day_num)
            self.skipped_days.append(day_num)
            return RoundResult(round_num=day_num, actions=[], completed=True)

        for event in events:
            event_emitter("experiment_action", event)
            logger.info(f"GAWorld emitted event: {event['agent']} {event['action']}")

        for agent_name, updates in state_updates.items():
            if agent_name in self.state.agents:
                self.state.agents[agent_name].properties.update(updates)

        return RoundResult(round_num=day_num, actions=[], completed=True)

    def _read_day_data(self, day_num: int) -> dict[str, Any]:
        if self._subprocess_manager is None:
            raise RuntimeError("gaworld.error.not_initialized")
        logger.info(
            f"GAWorld reading day {day_num} from "
            f"{self._subprocess_manager.output_dir if self._subprocess_manager else 'None'}"
        )

        memory_dir = self._subprocess_manager.output_dir / "memory"
        agents_data: list[dict[str, Any]] = []
        file_ids = self._agent_file_ids(memory_dir)
        if not file_ids:
            logger.warning(
                "GAWorld day %d: no agent file IDs found — memory_dir=%s, exists=%s, "
                "agent_name_map_keys=%s",
                day_num, memory_dir, memory_dir.exists(),
                list(self._agent_name_map.keys())[:5],
            )
            if memory_dir.exists():
                all_files = list(memory_dir.iterdir())
                logger.warning("GAWorld memory_dir files: %s", [f.name for f in all_files[:20]])
        for agent_id in file_ids:
            actions_path = memory_dir / f"agent_{agent_id}_actions.json"
            state_path = memory_dir / f"agent_{agent_id}.json"
            actions = json.loads(actions_path.read_text(encoding="utf-8")) if actions_path.exists() else []
            state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
            agent_data = {"id": agent_id, "actions": actions, "state": state}
            if isinstance(state, dict):
                agent_data.update(state)
            agents_data.append(agent_data)
        logger.info(f"GAWorld day {day_num} read {len(agents_data)} agent records from {len(file_ids)} file IDs")

        return {"day": day_num, "round": day_num, "agents": agents_data}

    def serialize_config(self) -> dict:
        data = super().serialize_config()
        data["config"]["agents"] = self.config.agents
        data["skipped_days"] = list(self.skipped_days)
        return data

    def is_complete(self) -> bool:
        return self.current_round >= self._sim_days
