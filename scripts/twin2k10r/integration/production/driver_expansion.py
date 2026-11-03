# This file runs one EXPANSION-style leg (one T2KX experiment x one
# blinding) against the frozen expansion pipeline, with the real
# respondent pool adapted to the pipeline's legacy field names. Records
# reuse the pipeline's own record shape (prompts, label maps, inference
# block, scoring) and gain the production provenance stamp: run id,
# dataset hash, and a plain-language status. Every record is flushed and
# force-synced the moment it is written, and a record already on disk is
# skipped on resume — never duplicated. Functions:
#   load_pipeline — the frozen expansion pipeline package (read-only).
#   run_leg       — execute or resume one expansion leg.
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


class ExpansionPipelineError(RuntimeError):
    """The frozen expansion pipeline is not usable on this machine."""


def load_pipeline():
    """Import the frozen expansion pipeline read-only and return it.

    The pipeline lives outside this repository copy; its parent directory
    is put on sys.path exactly like the existing integration adapter does.
    Raises ExpansionPipelineError when it cannot be imported (never a
    silent fallback to a different pipeline).
    """
    from twin2k10r.integration.expansion_pool import EXPANSION_PIPELINE_DIR

    parent = str(EXPANSION_PIPELINE_DIR.parent)
    if parent not in sys.path:
        sys.path.insert(0, parent)
    try:
        import pipeline.config  # noqa: F401  (read-only import)
        import pipeline.prompts
        import pipeline.registry
        import pipeline.scoring
        import pipeline.serving  # noqa: F401  (re-exported to callers)
        return sys.modules["pipeline"]
    except ImportError as exc:
        raise ExpansionPipelineError(
            f"cannot import the frozen expansion pipeline from "
            f"{EXPANSION_PIPELINE_DIR}: {exc}"
        ) from exc


def _now() -> str:
    """The current UTC time as an ISO-8601 string (record timestamps)."""
    return datetime.now(timezone.utc).isoformat()


def _retry(scorer, messages: list[dict], attempts: int = 4,
           backoff_seconds: float = 5.0):
    """One scorer call retried on transient failures, bounded.

    A definitive HTTP 4xx raises immediately (the frozen scorer reports
    transport failures as succeeded=False — retried, never recorded).
    """
    import pipeline.serving

    transient = (pipeline.serving.ServingError, TimeoutError,
                 ConnectionError, OSError)
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            result = scorer(messages)
            if result.get("succeeded", True):
                return result
            last_error = pipeline.serving.ServingError(
                "request returned failure: "
                f"{str(result.get('raw_logprob_response', ''))[:200]}")
        except transient as error:
            last_error = error
        if attempt < attempts:
            time.sleep(backoff_seconds * (2 ** (attempt - 1)))
    raise pipeline.serving.ServingError(
        f"request failed after {attempts} attempts: {last_error}")


def make_request_fn(pipeline, model: str, base_url: str):
    """The live first-token call function for one model on one server.

    Built on the frozen first-token scorer with the pipeline's own scan
    window and top-k, pointed at the RECONCILED server id.
    """
    from logprob_scoring import make_first_token_scorer
    from twin2k10 import registry as frozen_registry
    from twin2k10r.integration.production.model_ids import server_model_id

    return make_first_token_scorer(
        base_url,
        server_model_id(model),
        scan_tokens=pipeline.config.SCAN_TOKENS,
        top_k=pipeline.config.effective_top_k(),
        control_sequences=frozen_registry.control_sequences(model),
    )


def run_leg(
    run_dir,
    pipeline,
    model: str,
    base_url: str,
    exp_id: str,
    blinded: bool,
    personas: list[dict],
    run_id: str,
    dataset_sha256: str,
    request_fn=None,
) -> tuple[int, int]:
    """Execute (or resume) one expansion leg; returns (written, total).

    A record's identity is (persona_id, condition, item_index) — the
    pipeline's own resume key. Cells already durable are skipped; new
    records are written per-record flushed and fsynced.
    """
    entry = pipeline.registry.get(exp_id)
    spec = entry.spec
    blinding = "blinded" if blinded else "unblinded"
    from twin2k10 import registry as frozen_registry

    leg_dir = (
        Path(run_dir) / frozen_registry.safe_model_name(model)
        / f"{exp_id}_{blinding}"
    )
    leg_dir.mkdir(parents=True, exist_ok=True)
    records_path = leg_dir / "records.jsonl"
    done = pipeline.runner._load_done_keys(records_path)
    if request_fn is None:
        request_fn = make_request_fn(pipeline, model, base_url)
    labels_by_cell = _labels_of(pipeline, exp_id)

    written = 0
    planned = 0
    with records_path.open("a", encoding="utf-8") as handle:
        for persona_id, persona in enumerate(personas):
            for condition in spec.conditions:
                for item_index in range(len(condition.items)):
                    planned += 1
                    key = (persona_id, condition.name, item_index)
                    if key in done:
                        continue
                    record = _one_record(
                        pipeline, request_fn, model, exp_id, blinded,
                        persona_id, persona, condition.name, item_index,
                        run_id, dataset_sha256, labels_by_cell,
                    )
                    handle.write(json.dumps(record) + "\n")
                    handle.flush()
                    os.fsync(handle.fileno())
                    written += 1
    return written, planned


def _labels_of(pipeline, exp_id: str) -> dict[tuple[str, int], tuple]:
    """Each (condition, item_index)'s answer labels, resolved once."""
    entry = pipeline.registry.get(exp_id)
    labels: dict[tuple[str, int], tuple] = {}
    for condition in entry.spec.conditions:
        for item_index, item in enumerate(condition.items):
            labels[(condition.name, item_index)] = tuple(item.labels)
    return labels


def _one_record(
    pipeline, request_fn, model: str, exp_id: str, blinded: bool,
    persona_id: int, persona: dict, condition_name: str, item_index: int,
    run_id: str, dataset_sha256: str, labels_by_cell,
) -> dict:
    """Build, send, score and stamp ONE expansion record."""
    import hashlib

    fields = pipeline.prompts.item_record_fields(
        persona, exp_id, condition_name, item_index, blinded)
    labels = labels_by_cell[(condition_name, item_index)]
    raw = _retry(request_fn, [
        {"role": "system", "content": fields["system_prompt"]},
        {"role": "user", "content": fields["user_prompt"]},
    ])
    scored = pipeline.scoring.score_item(
        raw.get("top_logprobs") or [], labels)
    succeeded = bool(raw.get("succeeded"))
    from twin2k10r.integration.production.model_ids import server_model_id

    return {
        "run_id": run_id,
        "model": model,
        "model_id": server_model_id(model),
        "experiment": exp_id,
        "condition": condition_name,
        "item_index": item_index,
        "qid": fields["qid"],
        "blind": fields["blind"],
        "persona_id": persona_id,
        "dataset_sha256": dataset_sha256,
        "system_prompt": fields["system_prompt"],
        "user_prompt": fields["user_prompt"],
        "prompt_sha256": hashlib.sha256(
            (fields["system_prompt"] + "\x1e" + fields["user_prompt"])
            .encode("utf-8")).hexdigest(),
        "options_original": fields["options_original"],
        "label_map": fields["label_map"],
        "inference": fields["inference"],
        "ts": _now(),
        "status": "ok" if succeeded else "failed",
        **scored,
    }
