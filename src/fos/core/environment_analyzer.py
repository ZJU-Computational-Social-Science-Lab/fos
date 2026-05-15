"""Minimal environment analyzer stub.

Environment analysis was intentionally not migrated from the legacy codebase.
This stub unblocks backend imports. Actual analysis is a no-op.

TODO: Implement environment analyzer for fos if needed.

Contains: EnvironmentAnalyzer
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


class EnvironmentAnalyzer:
    """No-op environment analyzer stub.

    Returns empty suggestions — environment analysis is not implemented in fos.
    """

    def __init__(self, clients: Optional[Dict[str, Any]] = None) -> None:
        self.clients = clients

    def generate_suggestions(
        self,
        context: Dict[str, Any],
        count: int = 3,
    ) -> List[Dict[str, Any]]:
        """Return empty list — no environment suggestions available."""
        return []
