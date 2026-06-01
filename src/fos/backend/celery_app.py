from __future__ import annotations

import os

try:
    from celery import Celery
except ModuleNotFoundError:
    Celery = None

# Broker URL - prefer env var, fallback to redis localhost
BROKER_URL = os.environ.get("REDIS_URL") or os.environ.get("SOCIALSIM4_REDIS_URL") or "redis://localhost:6379/0"

if Celery is None:
    celery_app = None
else:
    celery_app = Celery("fos", broker=BROKER_URL)
    celery_app.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        task_track_started=True,
    )
