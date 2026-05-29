"""This file runs a GAWorld-backed experiment scene.

- GAWorldScene stores GAWorld-specific config values and run state.
- initialize sets up mapping and translator without starting subprocesses.
- _agent_id_from_config reads one agent ID from config.
- _agent_file_ids chooses the GAWorld agent output files to read.
- _launch_subprocess prepares GAWorld input files and starts run managers.
- _build_llm_env_overrides passes only GAWorld-specific LLM keys to GAWorld.
- _build_output_overrides tells GAWorld where to save every output file.
- _build_execution_profile_overrides picks the GAWorld runtime profile FOS uses.
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
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from fos.core.experiment.runner import RoundResult
from fos.core.experiment.scene import ExperimentScene
from fos.core.experiment.scenes.gaworld.profiles import export_profiles_csv, load_profiles
from fos.core.experiment.scenes.gaworld.subprocess_manager import GAWorldSubprocessManager
from fos.core.experiment.scenes.gaworld.translator import GAWorldOutputTranslator

logger = logging.getLogger(__name__)

GAWORLD_LLM_ENV_KEYS = (
    "GAWORLD_LLM_API_KEY",
    "MINIMAX_API_KEY",
    "ANTHROPIC_AUTH_TOKEN",
    "ANTHROPIC_API_KEY",
)
FOS_OLLAMA_PROVIDER_NAME = "fos_ollama"
DEFAULT_FOS_OLLAMA_BASE_URL = "http://127.0.0.1:11434"
DEFAULT_FOS_OLLAMA_MODEL = "qwen3:4b-instruct-2507-q4_K_M"
GAWORLD_WAIT_TIMEOUT_S = 1800
FAST_MODE_TIME_STEP_MINUTES = 120
DEFAULT_EXECUTION_PROFILE = "fast"


@dataclass(frozen=True)
class OllamaProviderSettings:
    """Stores the Ollama endpoint GAWorld needs."""

    base_url: str
    model: str
    timeout: int = 600


def _normalize_selected_agent_ids(raw_agent_ids: Any, agents: list[dict[str, Any]]) -> list[str]:
    """Chooses the requested GAWorld IDs from text first, then explicit agents."""
    if isinstance(raw_agent_ids, str):
        ids = [part.strip() for part in raw_agent_ids.split(",") if part.strip()]
        if ids:
            return ids
    elif isinstance(raw_agent_ids, list):
        ids = [str(agent_id).strip() for agent_id in raw_agent_ids if str(agent_id).strip()]
        if ids:
            return ids

    resolved_ids: list[str] = []
    for agent in agents:
        raw_agent_id = agent.get("id")
        if raw_agent_id is None:
            continue
        agent_id = str(raw_agent_id).strip()
        if agent_id:
            resolved_ids.append(agent_id)
    return resolved_ids


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


def _build_real_work_overrides(output_dir: Path, enabled: bool) -> dict[str, Any]:
    """Builds real-work paths under the FOS run folder and sets its mode."""
    work_dir = output_dir / "work"
    return {
        "enabled": enabled,
        "queue_path": str(work_dir / "queue.jsonl"),
        "artifacts_dir": str(work_dir),
        "capabilities_cache": str(work_dir / "capabilities.json"),
        "market": {
            "enabled": enabled,
            "store_path": str(work_dir / "market.jsonl"),
        },
    }


def _build_low_fidelity_runtime_overrides(output_dir: Path) -> dict[str, Any]:
    """Turns off expensive GAWorld behavior so FOS can finish days sooner."""
    return {
        "time_step_minutes": FAST_MODE_TIME_STEP_MINUTES,
        "vector_db_top_k": 1,
        "external_rag": {
            "bootstrap": {
                "enabled": False,
            },
        },
        "interests": {
            "enabled": False,
        },
        "news": {
            "enabled": False,
            "info_seek": {
                "enabled": False,
            },
        },
        "visualization": {
            "output_dir": str(output_dir / "visualization"),
            "enabled": False,
        },
        "routine_change": {
            "enabled": False,
        },
        "daily_planning": {
            "flexible": {
                "enabled": True,
                "min_items": 3,
                "max_items": 4,
                "max_time_shift_minutes": 60,
                "min_gap_minutes": 60,
                "allow_insertions": False,
            },
        },
        "spontaneity": {
            "enabled": False,
        },
        "memory": {
            "consolidation": {
                "enabled": False,
            },
            "decay": {
                "enabled": False,
            },
            "skill_consolidation": {
                "enabled": False,
            },
        },
        "dynamic_behavior": {
            "enabled": False,
        },
        "human_realism": {
            "enabled": False,
        },
        "fos_fast_mode": {
            "deterministic_cognition": True,
            "skip_daily_summary": True,
            "skip_daily_diary": True,
        },
    }


def _build_balanced_runtime_overrides() -> dict[str, Any]:
    """Keeps the main speedups without the most aggressive fast-mode shortcuts."""
    return {
        "time_step_minutes": FAST_MODE_TIME_STEP_MINUTES,
        "external_rag": {"bootstrap": {"enabled": False}},
        "news": {"enabled": False, "info_seek": {"enabled": False}},
        "dynamic_behavior": {"enabled": False},
        "human_realism": {"enabled": False},
        "fos_fast_mode": {},
    }


def _normalize_execution_profile(raw_value: Any) -> str:
    """Maps user input to one supported GAWorld execution profile."""
    profile = str(raw_value or DEFAULT_EXECUTION_PROFILE).strip().lower()
    if profile in {"fast", "balanced", "full_fidelity"}:
        return profile
    return DEFAULT_EXECUTION_PROFILE


def _build_execution_profile_overrides(profile: str, output_dir: Path) -> dict[str, Any]:
    """Returns runtime overrides for the selected GAWorld execution profile."""
    if profile == "full_fidelity":
        return {}
    if profile == "balanced":
        return _build_balanced_runtime_overrides()
    return _build_low_fidelity_runtime_overrides(output_dir)


def _build_hermetic_runtime_overrides(output_dir: Path, enable_real_work: bool = False) -> dict[str, Any]:
    """Turns off optional GAWorld services unless FOS explicitly re-enables them."""
    return {
        "environment_config_path": "",
        "external_environment_service": {
            "enabled": False,
        },
        "distributed": {
            "enabled": False,
            "local_agent_ids": [],
            "peer_agent_ids": [],
        },
        "extensions": {
            "strict": False,
            "hooks": {
                "on_simulation_start": [],
                "on_day_start": [],
                "on_time_tick": [],
                "on_agent_pre_step": [],
                "on_agent_post_step": [],
                "on_day_end": [],
                "on_simulation_end": [],
            },
        },
        "real_work": _build_real_work_overrides(output_dir, enabled=enable_real_work),
    }


def _ollama_generate_url(base_url: str) -> str:
    """Converts an Ollama server URL into GAWorld's generate endpoint URL."""
    clean_url = str(base_url or "").strip().rstrip("/")
    if not clean_url:
        clean_url = DEFAULT_FOS_OLLAMA_BASE_URL
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
    return OllamaProviderSettings(base_url=base_url or DEFAULT_FOS_OLLAMA_BASE_URL, model=model)


def _default_ollama_settings() -> OllamaProviderSettings:
    """Returns FOS's default local Ollama settings."""
    return OllamaProviderSettings(
        base_url=DEFAULT_FOS_OLLAMA_BASE_URL,
        model=DEFAULT_FOS_OLLAMA_MODEL,
    )


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
        self._agent_ids = _normalize_selected_agent_ids(params.get("agent_ids", []), config.agents)
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

        return _ollama_settings_from_env() or _default_ollama_settings()

    def _launch_subprocess(self) -> None:
        launch_started_at = time.perf_counter()
        profiles = load_profiles()
        if self._agent_ids:
            selected = set(self._agent_ids)
            profiles = [profile for profile in profiles if profile.id in selected]

        temp_dir = Path(tempfile.mkdtemp(prefix="gaworld_"))
        output_dir = Path(self.config.parameters.get("output_dir", temp_dir / "output"))
        enable_real_work = bool(self.config.parameters.get("enable_gaworld_real_work", False))
        execution_profile = _normalize_execution_profile(
            self.config.parameters.get("execution_profile", DEFAULT_EXECUTION_PROFILE)
        )
        config_overrides: dict[str, Any] = {
            "sim_days": self._sim_days,
            "seed": self._seed,
            **_build_output_overrides(output_dir),
            **_build_hermetic_runtime_overrides(
                output_dir=output_dir,
                enable_real_work=enable_real_work,
            ),
            **_build_execution_profile_overrides(execution_profile, output_dir),
        }
        if profiles:
            profiles_path = temp_dir / "profiles.csv"
            export_profiles_csv(profiles, profiles_path)
            config_overrides["csv_path"] = str(profiles_path)
        config_overrides["agent_ids"] = list(self._agent_ids)
        ollama_settings = self._resolve_ollama_settings()
        config_overrides.update(_build_ollama_config_overrides(ollama_settings))
        env_overrides: dict[str, str] = {}
        env_removals = set(GAWORLD_LLM_ENV_KEYS)

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
        logger.info(
            "GAWorld launch config: agent_ids=%s, profile_count=%d, hermetic=%s, "
            "external_environment_enabled=%s, distributed_enabled=%s",
            self._agent_ids,
            len(profiles),
            True,
            config_overrides["external_environment_service"]["enabled"],
            config_overrides["distributed"]["enabled"],
        )

        if bool(self.config.parameters.get("intervention_enabled", False)):
            event_config = dict(self.config.parameters.get("event_config", {}))
            self._comparative_managers = GAWorldSubprocessManager.launch_comparative(
                gaworld_path=gaworld_path,
                event_config=event_config,
                base_output_dir=output_dir,
                config_overrides=config_overrides,
                env_overrides=env_overrides,
                env_removals=env_removals,
            )
            self._subprocess_manager = self._comparative_managers[1]
            return

        manager = GAWorldSubprocessManager(
            gaworld_path=gaworld_path,
            config_overrides=config_overrides,
            output_dir=output_dir,
            preserve_output=True,
            env_overrides=env_overrides,
            env_removals=env_removals,
        )
        manager.launch()
        self._subprocess_manager = manager
        logger.info(
            "GAWorld subprocess launch prepared in %.3fs for output_dir=%s",
            time.perf_counter() - launch_started_at,
            output_dir,
        )

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
                logger.info(f"GAWorld output file: {output_dir / 'gaworld.log'}")
                logger.info(f"GAWorld diagnostic snapshot file: {output_dir / 'gaworld_wait_status.json'}")
        if self._subprocess_manager is None or self._translator is None:
            raise RuntimeError("gaworld.error.not_initialized")

        sim_state = self._subprocess_manager.wait_for_day(day_num, timeout=GAWORLD_WAIT_TIMEOUT_S)
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
