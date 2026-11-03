# This file holds the production run's safety rails: a circuit breaker
# that stops the whole queue after too many consecutive failures (a dead
# server must not grind through 15 models of garbage), a free-disk check
# taken before each model block, the run's PID file, atomic JSON writes,
# and the PROGRESS file the operator tails while the run is going.
# Functions / classes:
#   CircuitBreaker      — consecutive-failure guard (raises CircuitOpenError).
#   check_disk          — abort before starting when disk is clearly too low.
#   write_pid_file      — the run's PID + start time, for stop/resume.
#   write_progress      — an atomic PROGRESS.json snapshot (tail-friendly).
#   write_atomic_json   — a JSON payload no reader ever sees half-written.
from __future__ import annotations

import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

# Run aborts when free disk on the run folder drops below this (records
# are a few KB each; 2 GiB still holds hundreds of thousands of records).
MIN_FREE_DISK_BYTES = 2 * 1024 ** 3

# Consecutive failed records allowed before the breaker opens the circuit.
DEFAULT_MAX_CONSECUTIVE_FAILURES = 5


class CircuitOpenError(RuntimeError):
    """The circuit breaker opened: too many consecutive failures."""


class LowDiskError(RuntimeError):
    """Free disk space is below the safety floor."""


class CircuitBreaker:
    """Counts consecutive failed records; opens the circuit past the cap.

    A success resets the count (one flaky answer must not kill a run;
    a dead server must). check() raises CircuitOpenError once the count
    reaches max_consecutive_failures.
    """

    def __init__(self, max_consecutive_failures: int =
                 DEFAULT_MAX_CONSECUTIVE_FAILURES):
        self.max_consecutive_failures = max_consecutive_failures
        self.consecutive_failures = 0

    def record_success(self) -> None:
        """One good record: the consecutive-failure count restarts."""
        self.consecutive_failures = 0

    def record_failure(self) -> None:
        """One bad record: the count grows toward the cap."""
        self.consecutive_failures += 1

    def check(self) -> None:
        """Raise CircuitOpenError when the failure cap is reached."""
        if self.consecutive_failures >= self.max_consecutive_failures:
            raise CircuitOpenError(
                f"circuit breaker opened after "
                f"{self.consecutive_failures} consecutive failed records"
            )


def check_disk(run_dir) -> None:
    """Abort (loudly, with the numbers) if free disk is below the floor."""
    free = shutil.disk_usage(run_dir).free
    if free < MIN_FREE_DISK_BYTES:
        raise LowDiskError(
            f"only {free / 1024 ** 3:.1f} GiB free on {run_dir} "
            f"(need {MIN_FREE_DISK_BYTES / 1024 ** 3:.0f} GiB)"
        )


def write_pid_file(run_dir) -> Path:
    """The run's PID file: pid and start time, for stop/resume tooling."""
    path = Path(run_dir) / "runner.pid"
    payload = {
        "pid": os.getpid(),
        "started": datetime.now(timezone.utc).isoformat(),
    }
    write_atomic_json(path, payload)
    return path


def write_progress(run_dir, progress: dict) -> Path:
    """An atomic PROGRESS.json snapshot the operator can tail safely."""
    path = Path(run_dir) / "PROGRESS.json"
    payload = {**progress, "updated_at":
               datetime.now(timezone.utc).isoformat()}
    write_atomic_json(path, payload)
    return path


def write_atomic_json(path, payload: dict) -> None:
    """Write a JSON payload so no reader ever sees a partial file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = None, None
    import tempfile

    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    except BaseException:
        if tmp_name and os.path.exists(tmp_name):
            os.unlink(tmp_name)
        raise
