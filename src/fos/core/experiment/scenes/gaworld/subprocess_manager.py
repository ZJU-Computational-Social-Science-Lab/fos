"""This file starts, watches, and stops GAWorld subprocess runs.

- GAWorldProcessError is raised when the GAWorld process exits before work is done.
- GAWorldTimeoutError is raised when waiting takes too long.
- GAWorldSubprocessManager stores run settings and controls one GAWorld subprocess.
- launch starts the GAWorld simulator process with config overrides in env.
- wait_for_day keeps checking state output until a target day is reached.
- is_alive tells whether the subprocess is still running.
- kill stops the process and optionally removes run output.
- launch_comparative starts baseline and treatment runs and returns both managers.
"""

from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class GAWorldProcessError(RuntimeError):
    """Raised when the GAWorld process exits unexpectedly."""


class GAWorldTimeoutError(RuntimeError):
    """Raised when waiting for GAWorld output reaches timeout."""


@dataclass
class GAWorldSubprocessManager:
    """Controls one GAWorld simulator process and its output folder."""

    gaworld_path: Path
    config_overrides: dict[str, Any]
    output_dir: Path
    preserve_output: bool = False
    process: subprocess.Popen[str] | Any | None = field(default=None, init=False)

    def launch(self) -> None:
        """Starts the simulator process with config overrides in environment."""
        script_path = self.gaworld_path / "generative_city_sim.py"
        if not script_path.exists():
            raise FileNotFoundError("gaworld.error.script_not_found")

        command = [sys.executable, str(script_path), "run"]
        env = os.environ.copy()
        env["GAWORLD_CONFIG_OVERRIDES"] = json.dumps(self.config_overrides)
        existing_pythonpath = env.get("PYTHONPATH", "")
        gaworld_dir = str(self.gaworld_path)
        if existing_pythonpath:
            env["PYTHONPATH"] = gaworld_dir + os.pathsep + existing_pythonpath
        else:
            env["PYTHONPATH"] = gaworld_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

        if os.name == "nt":
            self.process = subprocess.Popen(command, env=env, cwd=str(self.gaworld_path))
            return

        self.process = subprocess.Popen(
            command,
            env=env,
            cwd=str(self.gaworld_path),
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

        baseline = cls(gaworld_path, baseline_overrides, base_output_dir / "baseline")
        treatment = cls(gaworld_path, treatment_overrides, base_output_dir / "treatment")
        baseline.launch()
        treatment.launch()
        return baseline, treatment
