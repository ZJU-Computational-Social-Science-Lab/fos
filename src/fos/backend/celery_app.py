from __future__ import annotations

import os

try:
    from celery import Celery
except ModuleNotFoundError:  # pragma: no cover - exercised via import-time fallback test
    Celery = None

# Broker URL - prefer env var, fallback to redis localhost
BROKER_URL = os.environ.get("REDIS_URL") or os.environ.get("SOCIALSIM4_REDIS_URL") or "redis://localhost:6379/0"


class _NoopCeleryControl:
    """Provides the small revoke API local runs may call."""

    def revoke(self, _task_id: str | None, terminate: bool = False) -> None:
        return None


class _NoopConfig(dict):
    """Keeps the same update method shape as Celery's config object."""


class _NoopCeleryApp:
    """Lets backend startup continue when Celery is not installed locally."""

    def __init__(self) -> None:
        self.control = _NoopCeleryControl()
        self.conf = _NoopConfig()
        self.is_available = False


if Celery is None:
    celery_app = _NoopCeleryApp()
else:
    celery_app = Celery("fos", broker=BROKER_URL)
    celery_app.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        task_track_started=True,
    )
    celery_app.is_available = True
