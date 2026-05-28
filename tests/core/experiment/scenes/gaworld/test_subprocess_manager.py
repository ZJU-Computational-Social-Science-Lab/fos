"""This file tests the GAWorld subprocess manager behavior.

- test_constructor_starts_with_no_process checks the manager starts with process set to None.
- test_is_alive_false_when_process_is_none checks is_alive returns False with no process.
- test_is_alive_true_when_poll_returns_none checks is_alive returns True when subprocess is running.
- test_wait_for_day_returns_state_when_target_day_reached checks wait_for_day returns parsed state at target day.
- test_wait_for_day_raises_process_error_when_process_exits checks wait_for_day raises process error if process exits unexpectedly.
- test_wait_for_day_raises_timeout_error_when_deadline_passes checks wait_for_day raises timeout while process stays alive.
- test_kill_calls_terminate_on_windows checks kill calls terminate on Windows.
- test_kill_preserves_output_directory_when_requested checks kill does not delete output when preserve_output is True.
- test_launch_adds_gaworld_path_to_subprocess_pythonpath checks child imports can find GAWorld modules.
- test_launch_adds_env_overrides_to_subprocess_environment checks caller-provided env vars are sent to GAWorld.
- test_launch_forces_utf8_io_in_subprocess_environment checks child Python uses UTF-8 I/O.
- test_launch_writes_subprocess_output_to_gaworld_log checks child output is captured to a run log.
- test_launch_comparative_returns_two_manager_instances checks launch_comparative returns two launched managers.
"""

import json
import os
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from fos.core.experiment.scenes.gaworld.subprocess_manager import (
    GAWorldProcessError,
    GAWorldSubprocessManager,
    GAWorldTimeoutError,
    _resolve_python_executable,
)


def test_constructor_starts_with_no_process(tmp_path: Path) -> None:
    manager = GAWorldSubprocessManager(tmp_path, {}, tmp_path / "out")
    assert manager.process is None


def test_is_alive_false_when_process_is_none(tmp_path: Path) -> None:
    manager = GAWorldSubprocessManager(tmp_path, {}, tmp_path / "out")
    assert manager.is_alive() is False


def test_is_alive_true_when_poll_returns_none(tmp_path: Path) -> None:
    manager = GAWorldSubprocessManager(tmp_path, {}, tmp_path / "out")
    manager.process = SimpleNamespace(poll=lambda: None)
    assert manager.is_alive() is True


def test_wait_for_day_returns_state_when_target_day_reached(tmp_path: Path) -> None:
    output_dir = tmp_path / "out"
    memory_dir = output_dir / "memory"
    memory_dir.mkdir(parents=True)
    state = {"last_day": 3, "x": 1}
    (memory_dir / "sim_state.json").write_text(json.dumps(state), encoding="utf-8")

    manager = GAWorldSubprocessManager(tmp_path, {}, output_dir)
    manager.process = SimpleNamespace(poll=lambda: None)

    result = manager.wait_for_day(day=2, timeout=0.1, poll_interval=0.01)
    assert result == state


def test_wait_for_day_raises_process_error_when_process_exits(tmp_path: Path) -> None:
    manager = GAWorldSubprocessManager(tmp_path, {}, tmp_path / "out")
    manager.process = SimpleNamespace(poll=lambda: 1)

    with pytest.raises(GAWorldProcessError, match="exited unexpectedly"):
        manager.wait_for_day(day=1, timeout=0.05, poll_interval=0.01)


def test_wait_for_day_raises_timeout_error_when_deadline_passes(tmp_path: Path) -> None:
    output_dir = tmp_path / "out"
    (output_dir / "memory").mkdir(parents=True)

    manager = GAWorldSubprocessManager(tmp_path, {}, output_dir)
    manager.process = SimpleNamespace(poll=lambda: None)

    with pytest.raises(GAWorldTimeoutError):
        manager.wait_for_day(day=10, timeout=0.05, poll_interval=0.01)


def test_kill_calls_terminate_on_windows(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    called = {"terminate": False}

    def _terminate() -> None:
        called["terminate"] = True

    manager = GAWorldSubprocessManager(tmp_path, {}, tmp_path / "out")
    manager.process = SimpleNamespace(terminate=_terminate, poll=lambda: None)

    monkeypatch.setattr("os.name", "nt")
    manager.kill()

    assert called["terminate"] is True


def test_kill_preserves_output_directory_when_requested(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    output_dir = tmp_path / "out"
    output_dir.mkdir(parents=True)

    manager = GAWorldSubprocessManager(tmp_path, {}, output_dir, preserve_output=True)
    manager.process = SimpleNamespace(terminate=lambda: None, poll=lambda: None)

    monkeypatch.setattr("os.name", "nt")
    manager.kill()

    assert output_dir.exists()


def test_launch_adds_gaworld_path_to_subprocess_pythonpath(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gaworld_path = tmp_path / "GAWorld"
    output_dir = tmp_path / "out"
    gaworld_path.mkdir()
    (gaworld_path / "generative_city_sim.py").write_text("print('ok')", encoding="utf-8")
    monkeypatch.setenv("PYTHONPATH", "existing_path")
    captured: dict[str, object] = {}

    def _fake_popen(command: list[str], **kwargs: object) -> SimpleNamespace:
        captured["command"] = command
        captured.update(kwargs)
        return SimpleNamespace(poll=lambda: None)

    monkeypatch.setattr("subprocess.Popen", _fake_popen)

    manager = GAWorldSubprocessManager(gaworld_path, {"seed": 7}, output_dir)
    manager.launch()

    env = captured["env"]
    assert isinstance(env, dict)
    assert captured["cwd"] == str(gaworld_path)
    # PYTHONPATH must start with gaworld_path and preserve existing entries.
    # Additional gaworld package dirs may also be present.
    pythonpath_parts = env["PYTHONPATH"].split(os.pathsep)
    assert str(gaworld_path) in pythonpath_parts
    assert "existing_path" in pythonpath_parts
    assert json.loads(env["GAWORLD_CONFIG_OVERRIDES"]) == {"seed": 7}


def test_launch_adds_env_overrides_to_subprocess_environment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gaworld_path = tmp_path / "GAWorld"
    output_dir = tmp_path / "out"
    gaworld_path.mkdir()
    (gaworld_path / "generative_city_sim.py").write_text("print('ok')", encoding="utf-8")
    captured: dict[str, object] = {}

    def _fake_popen(command: list[str], **kwargs: object) -> SimpleNamespace:
        captured.update(kwargs)
        return SimpleNamespace(poll=lambda: None)

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr("subprocess.Popen", _fake_popen)

    manager = GAWorldSubprocessManager(
        gaworld_path,
        {},
        output_dir,
        env_overrides={"ANTHROPIC_API_KEY": "from-fos"},
    )
    manager.launch()

    env = captured["env"]
    assert isinstance(env, dict)
    assert env["ANTHROPIC_API_KEY"] == "from-fos"


def test_launch_writes_subprocess_output_to_gaworld_log(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gaworld_path = tmp_path / "GAWorld"
    output_dir = tmp_path / "out"
    gaworld_path.mkdir()
    (gaworld_path / "generative_city_sim.py").write_text("print('ok')", encoding="utf-8")
    captured: dict[str, object] = {}

    def _fake_popen(command: list[str], **kwargs: object) -> SimpleNamespace:
        captured["command"] = command
        captured.update(kwargs)
        stdout = kwargs["stdout"]
        assert hasattr(stdout, "write")
        stdout.write("child output")
        return SimpleNamespace(poll=lambda: None)

    monkeypatch.setattr("subprocess.Popen", _fake_popen)

    manager = GAWorldSubprocessManager(gaworld_path, {}, output_dir)
    manager.launch()

    assert captured["stderr"] is subprocess.STDOUT
    assert (output_dir / "gaworld.log").read_text(encoding="utf-8") == "child output"


def test_launch_forces_utf8_io_in_subprocess_environment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gaworld_path = tmp_path / "GAWorld"
    output_dir = tmp_path / "out"
    gaworld_path.mkdir()
    (gaworld_path / "generative_city_sim.py").write_text("print('ok')", encoding="utf-8")
    captured: dict[str, object] = {}

    def _fake_popen(command: list[str], **kwargs: object) -> SimpleNamespace:
        captured.update(kwargs)
        return SimpleNamespace(poll=lambda: None)

    monkeypatch.setattr("subprocess.Popen", _fake_popen)

    manager = GAWorldSubprocessManager(gaworld_path, {}, output_dir)
    manager.launch()

    env = captured["env"]
    assert isinstance(env, dict)
    assert env["PYTHONUTF8"] == "1"
    assert env["PYTHONIOENCODING"] == "utf-8"


def test_launch_comparative_returns_two_manager_instances(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    launched: list[GAWorldSubprocessManager] = []

    def _fake_launch(self: GAWorldSubprocessManager) -> None:
        launched.append(self)
        self.process = SimpleNamespace(poll=lambda: None)

    monkeypatch.setattr(GAWorldSubprocessManager, "launch", _fake_launch)

    baseline, treatment = GAWorldSubprocessManager.launch_comparative(
        gaworld_path=tmp_path,
        event_config={"name": "shock"},
        base_output_dir=tmp_path / "runs",
        config_overrides={"seed": 7},
    )

    assert isinstance(baseline, GAWorldSubprocessManager)
    assert isinstance(treatment, GAWorldSubprocessManager)
    assert len(launched) == 2


def test_resolve_python_executable_returns_sys_executable_by_default(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """When sys.executable is a valid absolute path, it is returned as-is."""
    fake_python_path = tmp_path / ("python.exe" if os.name == "nt" else "python3")
    fake_python_path.write_text("fake", encoding="utf-8")
    fake_python = str(fake_python_path)
    monkeypatch.setattr("sys.executable", fake_python, raising=False)
    monkeypatch.setattr("os.path.isfile", lambda p: True)

    result = _resolve_python_executable()
    assert result == fake_python


def test_resolve_python_executable_falls_back_to_conda_prefix(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """When sys.executable is empty, conda prefix is used to find Python."""
    monkeypatch.setattr("sys.executable", "", raising=False)
    monkeypatch.setattr("os.path.isabs", lambda p: False if p == "" else True)

    conda_dir = tmp_path / "conda_env"
    conda_dir.mkdir()
    python_exe = conda_dir / "python.exe"
    python_exe.write_text("fake", encoding="utf-8")
    monkeypatch.setenv("CONDA_PREFIX", str(conda_dir))
    monkeypatch.setattr("os.name", "nt")
    monkeypatch.setattr("os.path.isfile", lambda p: Path(p).exists())

    result = _resolve_python_executable()
    assert result == str(python_exe)


def test_resolve_python_executable_falls_back_to_exec_prefix(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """When sys.executable and CONDA_PREFIX are both absent, exec_prefix is used."""
    monkeypatch.setattr("sys.executable", "", raising=False)
    monkeypatch.setattr("os.path.isabs", lambda p: False if p == "" else True)
    monkeypatch.setattr("sys.exec_prefix", str(tmp_path), raising=False)
    monkeypatch.delenv("CONDA_PREFIX", raising=False)
    monkeypatch.setattr("os.name", "nt")
    python_exe = tmp_path / "python.exe"
    python_exe.write_text("fake", encoding="utf-8")
    monkeypatch.setattr("os.path.isfile", lambda p: Path(p).exists())

    result = _resolve_python_executable()
    assert result == str(python_exe)


def test_launch_uses_resolved_python_executable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """launch() uses _resolve_python_executable instead of raw sys.executable."""
    gaworld_path = tmp_path / "GAWorld"
    output_dir = tmp_path / "out"
    gaworld_path.mkdir()
    (gaworld_path / "generative_city_sim.py").write_text("print('ok')", encoding="utf-8")

    captured_command: list[str] = []

    def _fake_popen(command: list[str], **kwargs: object) -> SimpleNamespace:
        captured_command.extend(command)
        return SimpleNamespace(poll=lambda: None)

    monkeypatch.setattr("subprocess.Popen", _fake_popen)
    monkeypatch.setattr("os.name", "nt")
    # Force _resolve_python_executable to return a specific path
    monkeypatch.setattr(
        "fos.core.experiment.scenes.gaworld.subprocess_manager._resolve_python_executable",
        lambda: "/custom/python",
    )

    manager = GAWorldSubprocessManager(gaworld_path, {}, output_dir)
    manager.launch()

    assert captured_command[0] == "/custom/python"


def test_launch_includes_gaworld_package_dirs_in_pythonpath(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """launch() adds gaworld package directories to PYTHONPATH."""
    gaworld_path = tmp_path / "GAWorld"
    output_dir = tmp_path / "out"
    gaworld_path.mkdir()
    (gaworld_path / "generative_city_sim.py").write_text("print('ok')", encoding="utf-8")

    captured: dict[str, object] = {}

    def _fake_popen(command: list[str], **kwargs: object) -> SimpleNamespace:
        captured["env"] = kwargs.get("env", {})
        return SimpleNamespace(poll=lambda: None)

    monkeypatch.setattr("subprocess.Popen", _fake_popen)
    monkeypatch.setattr("os.name", "nt")
    monkeypatch.setattr(
        "fos.core.experiment.scenes.gaworld.subprocess_manager._gaworld_package_dirs",
        lambda: ["/site-packages/gaworld-parent"],
    )

    manager = GAWorldSubprocessManager(gaworld_path, {}, output_dir)
    manager.launch()

    env = captured["env"]
    assert isinstance(env, dict)
    pythonpath = env["PYTHONPATH"]
    assert str(gaworld_path) in pythonpath
    assert "/site-packages/gaworld-parent" in pythonpath
