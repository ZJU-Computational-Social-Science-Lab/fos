"""Helpers for running one simulation tree step.

run_simulator_for_advance runs a simulator and returns runtime problems instead
of hiding them, so the caller can still show the node logs to the user.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any


logger = logging.getLogger(__name__)


async def run_simulator_for_advance(
    simulator: Any,
    max_turns: int,
) -> RuntimeError | FileNotFoundError | None:
    """Run a simulator step and return user-visible runtime failures."""
    try:
        await asyncio.to_thread(simulator.run, max_turns=max_turns)
    except (RuntimeError, FileNotFoundError) as error:
        logger.exception("simulation runtime failed during tree advance")
        return error
    runtime_error = getattr(simulator, "last_runtime_error", None)
    if isinstance(runtime_error, RuntimeError):
        return runtime_error
    return None
