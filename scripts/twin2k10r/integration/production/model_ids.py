# This file is the production run's model name map. Records keep the
# historical study ids (so analysis joins the frozen runs cleanly), but
# requests must use the names the local model library answers to TODAY.
# Every mapping below was verified on 2026-11-03 to point at the exact
# same GGUF weights file (same path, same byte size) the historical runs
# served — 6 exact matches and 9 name-drifts, nothing substituted.
# Functions:
#   server_model_id — the current server id for one study record id.
from __future__ import annotations

# Study record id -> the server id the local library serves today.
# Keys are the frozen record ids; only the 9 drifted values differ from
# the historical map (per MODEL_ID_RECONCILIATION.md, Task 3137).
RECONCILED_MODEL_IDS: dict[str, str] = {
    # Exact matches — the name never changed.
    "gpt-oss-20b": "openai/gpt-oss-20b",
    "gemma-4-26b-a4b": "google/gemma-4-26b-a4b",
    "qwen3.8-27b": "qwen/qwen3.8-27b",
    "qwen3.6-35b-a3b": "qwen/qwen3.6-35b-a3b",
    "qwen3-32b": "qwen/qwen3-32b",
    "qwen3.6-35b-a3b-uncensored": (
        "qwen3.6-35b-a3b-uncensored-hauhaucs-aggressive"
    ),
    "muse-glimmer": "meta/muse-glimmer",
    # Name drifts, SAME weights (verified by GGUF path + byte size).
    "gemma-4-31b-it-qat": "google/gemma-4-31b-qat",
    "gemma-4-12b-it-qat": "google/gemma-4-12b-qat",
    "qwen3.6-27b-dense": "qwen/qwen3.6-27b",
    "qwen3-4b": "qwen/qwen3-4b-2507",
    "granite-4.1-8b": "granite-4.1-8b",
    # TRAP: two granite-4.1-30b files exist on disk; ONLY the
    # lmstudio-community Q4_K_M is the historical file (unsloth is a
    # different quant). Never switch this entry.
    "granite-4.1-30b": "lmstudio-community/granite-4.1-30b",
    "nemotron-cascade-2-30b-a3b": "nvidia_nemotron-cascade-2-30b-a3b",
    "glm-4.7-flash": "zai-org/glm-4.7-flash",
}


class UnknownModelError(ValueError):
    """The study id given is not one of the production 15."""


def server_model_id(model: str) -> str:
    """The server id one study record id must be requested under.

    Raises UnknownModelError for a typo — a typo must stop the run,
    never invent a model.
    """
    try:
        return RECONCILED_MODEL_IDS[model]
    except KeyError:
        raise UnknownModelError(
            f"unknown study model {model!r} — not one of the production "
            "model ids"
        ) from None
