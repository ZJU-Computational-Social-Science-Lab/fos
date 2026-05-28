"""This file starts, watches, and stops GAWorld subprocess runs.

- _resolve_python_executable finds the right Python for the subprocess.
- _gaworld_package_dirs locates the gaworld package for PYTHONPATH setup.
- GAWorldProcessError is raised when the GAWorld process exits before work is done.
- GAWorldTimeoutError is raised when waiting takes too long.
- GAWorldSubprocessManager stores run settings and controls one GAWorld subprocess.
- launch starts the GAWorld simulator process with config overrides in env.
- env_overrides lets the scene add needed environment values for the subprocess.
- wait_for_day keeps checking state output until a target day is reached.
- is_alive tells whether the subprocess is still running.
- kill stops the process and optionally removes run output.
- launch_comparative starts baseline and treatment runs and returns both managers.
"""

from __future__ import annotations

import importlib.util
import json
import logging
import os
import shutil
import signal
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class GAWorldProcessError(RuntimeError):
    """Raised when the GAWorld process exits unexpectedly."""


class GAWorldTimeoutError(RuntimeError):
    """Raised when waiting for GAWorld output reaches timeout."""


def _resolve_python_executable() -> str:
    """Resolve the Python executable to use for the GAWorld subprocess.

    Uses sys.executable by default. Falls back to CONDA_PREFIX or
    sys.exec_prefix when sys.executable is unavailable or unreliable,
    such as when running inside a uvicorn worker on Windows.

    Returns:
        Absolute path to the Python executable.
    """
    # Primary: sys.executable should normally be correct
    if sys.executable and os.path.isabs(sys.executable) and os.path.isfile(sys.executable):
        return sys.executable

    # Fallback 1: CONDA_PREFIX (set when a conda environment is activated)
    conda_prefix = os.environ.get("CONDA_PREFIX")
    if conda_prefix:
        if os.name == "nt":
            candidate = os.path.join(conda_prefix, "python.exe")
        else:
            candidate = os.path.join(conda_prefix, "bin", "python")
        if os.path.isfile(candidate):
            logger.info("GAWorld: using CONDA_PREFIX Python: %s", candidate)
            return candidate

    # Fallback 2: sys.exec_prefix (works for virtualenvs and venvs)
    if os.name == "nt":
        candidate = os.path.join(sys.exec_prefix, "python.exe")
    else:
        candidate = os.path.join(sys.exec_prefix, "bin", "python")
    if os.path.isfile(candidate):
        logger.info("GAWorld: using exec_prefix Python: %s", candidate)
        return candidate

    # Fallback 3: PATH lookup
    which_python = shutil.which("python")
    if which_python:
        logger.info("GAWorld: using PATH-resolved Python: %s", which_python)
        return which_python

    # Last resort: return whatever sys.executable is, or "python"
    logger.warning("GAWorld: could not resolve a reliable Python, falling back")
    return sys.executable or "python"


def _gaworld_package_dirs() -> list[str]:
    """Find directories needed on PYTHONPATH for gaworld imports.

    Returns parent directories of the gaworld package so that
    ``import gaworld`` works in the subprocess regardless of which
    Python interpreter is used.
    """
    dirs: list[str] = []
    try:
        spec = importlib.util.find_spec("gaworld")
        if spec is not None:
            if spec.submodule_search_locations:
                parent = str(Path(spec.submodule_search_locations[0]).parent)
                dirs.append(parent)
            elif spec.origin:
                parent = str(Path(spec.origin).parent)
                dirs.append(parent)
    except (ModuleNotFoundError, ValueError):
        pass
    return dirs


@dataclass
class GAWorldSubprocessManager:
    """Controls one GAWorld simulator process and its output folder."""

    gaworld_path: Path
    config_overrides: dict[str, Any]
    output_dir: Path
    preserve_output: bool = False
    env_overrides: dict[str, str] = field(default_factory=dict)
    process: subprocess.Popen[str] | Any | None = field(default=None, init=False)

    def launch(self) -> None:
        """Starts the simulator process with config overrides in environment."""
        script_path = self.gaworld_path / "generative_city_sim.py"
        if not script_path.exists():
            raise FileNotFoundError("gaworld.error.script_not_found")

        python_exe = _resolve_python_executable()
        command = [python_exe, str(script_path), "run"]
        env = os.environ.copy()
        env.update({key: value for key, value in self.env_overrides.items() if value})
        env["GAWORLD_CONFIG_OVERRIDES"] = json.dumps(self.config_overrides)
        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        logger.info(
            "GAWorld env API keys present: ANTHROPIC_API_KEY=%s, MINIMAX_API_KEY=%s, "
            "ANTHROPIC_AUTH_TOKEN=%s",
            bool(env.get("ANTHROPIC_API_KEY")),
            bool(env.get("MINIMAX_API_KEY")),
            bool(env.get("ANTHROPIC_AUTH_TOKEN")),
        )

        # Build PYTHONPATH: gaworld script dir + gaworld package dirs
        path_entries: list[str] = [str(self.gaworld_path)]
        for pkg_dir in _gaworld_package_dirs():
            if pkg_dir not in path_entries:
                path_entries.append(pkg_dir)

        existing_pythonpath = env.get("PYTHONPATH", "")
        new_pythonpath = os.pathsep.join(path_entries)
        env["PYTHONPATH"] = new_pythonpath + (
            os.pathsep + existing_pythonpath if existing_pythonpath else ""
        )

        self.output_dir.mkdir(parents=True, exist_ok=True)
        log_file = self.output_dir / "gaworld.log"

        logger.info(
            "GAWorld launch: python=%s, prefix=%s, exec_prefix=%s, "
            "CONDA_PREFIX=%s, PYTHONPATH=%s",
            python_exe,
            sys.prefix,
            sys.exec_prefix,
            os.environ.get("CONDA_PREFIX"),
            env["PYTHONPATH"],
        )

        if os.name == "nt":
            with open(log_file, "w", encoding="utf-8") as file_obj:
                self.process = subprocess.Popen(
                    command,
                    env=env,
                    cwd=str(self.gaworld_path),
                    stdout=file_obj,
                    stderr=subprocess.STDOUT,
                )
            return

        with open(log_file, "w", encoding="utf-8") as file_obj:
            self.process = subprocess.Popen(
                command,
                env=env,
                cwd=str(self.gaworld_path),
                stdout=file_obj,
                stderr=subprocess.STDOUT,
                preexec_fn=os.setsid,
            )

    def wait_for_day(
        self,
        day: int,
        timeout: float = 300,
        poll_interval: float = 3.0,
    ) -> dict[str, Any]:
        """Waits for sim_state.json to report last_day at or beyond target day."""
        deadline = time.time() + timeout
        state_path = self.output_dir / "memory" / "sim_state.json"

        while True:
            if self.process is not None:
                exit_code = self.process.poll()
                if exit_code is not None and exit_code != 0:
                    raise GAWorldProcessError("gaworld.error.exited_unexpectedly: exited unexpectedly")

            if state_path.exists():
                state = json.loads(state_path.read_text(encoding="utf-8"))
                if int(state.get("last_day", -1)) >= day:
                    return state

            if time.time() > deadline:
                raise GAWorldTimeoutError("gaworld.error.wait_timeout")

            time.sleep(poll_interval)

    def is_alive(self) -> bool:
        """Returns True only when a process exists and is still running."""
        return self.process is not None and self.process.poll() is None

    def kill(self) -> None:
        """Stops the process and removes output unless output preservation is enabled."""
        if self.process is not None and self.process.poll() is None:
            if os.name == "nt":
                self.process.terminate()
            else:
                os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)

        if not self.preserve_output and self.output_dir.exists():
            shutil.rmtree(self.output_dir)

    @classmethod
    def launch_comparative(
        cls,
        gaworld_path: Path,
        event_config: dict[str, Any],
        base_output_dir: Path,
        config_overrides: dict[str, Any],
        env_overrides: dict[str, str] | None = None,
    ) -> tuple[GAWorldSubprocessManager, GAWorldSubprocessManager]:
        """Starts baseline and treatment runs and returns both managers."""
        baseline_overrides = {
            **config_overrides,
            "intervention": {"enabled": False},
        }
        treatment_overrides = {
            **config_overrides,
            "intervention": {"enabled": True, **event_config},
        }

        baseline = cls(
            gaworld_path,
            baseline_overrides,
            base_output_dir / "baseline",
            env_overrides=env_overrides or {},
        )
        treatment = cls(
            gaworld_path,
            treatment_overrides,
            base_output_dir / "treatment",
            env_overrides=env_overrides or {},
        )
        baseline.launch()
        treatment.launch()
        return baseline, treatment
