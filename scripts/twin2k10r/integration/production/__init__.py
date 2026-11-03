# This file maps each production model's study record id to the server id
# the LOCAL llama-server answers to today. The historical names drifted on
# disk (the model files were renamed), and the 2026-11-03 reconciliation
# verified that every current name points at the EXACT same GGUF weights
# file the frozen runs served (same path, same byte size). Records keep the
# historical record ids so analysis joins cleanly; only requests use the
# current names. Functions:
#   server_model_id — the current server id for one record id (raises on
#                     an unknown model instead of inventing one).
from twin2k10r.integration.production.model_ids import (  # noqa: F401
    RECONCILED_MODEL_IDS,
    UnknownModelError,
    server_model_id,
)
