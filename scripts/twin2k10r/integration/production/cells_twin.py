# This file executes ONE twin-style measurement cell: it turns a
# (persona, experiment, arm, blinding) cell into the exact prompts, makes
# ONE first-token call per item of the arm (a choice letter call on its
# own prompt, a digit call on its own prompt), folds every call's top-k
# into the item's label distribution, and stamps a full record with its
# provenance (run id, dataset hash, persona id, prompt hash, status). A
# failed call still produces a kept record flagged failed — never a
# silent retry-hiding row. This module holds no loop and no file writing.
# Functions:
#   merged_stimuli     — the question catalogue both pipelines share.
#   make_scorers       — the choice and digit first-token scorers.
#   inference_settings — the pinned inference block stamped on records.
#   execute_cell       — one cell end to end, returning its record.
from __future__ import annotations

import hashlib
import time
from datetime import datetime, timezone

from twin2k10 import legexec
from twin2k10r.integration.production import prompts_twin
from twin2k10r.integration.production.model_ids import server_model_id


def merged_stimuli() -> dict[str, dict]:
    """The twin+restored question catalogue, keyed by question id."""
    return prompts_twin.merged_stimuli()


def inference_settings(base_url: str) -> dict:
    """The pinned inference settings every twin record carries."""
    return legexec.inference_settings(base_url)


def make_scorers(model: str, base_url: str, stimuli: dict):
    """The (choice, digit) first-token scorer pair for one model.

    Reuses the frozen legexec builders, pointed at the RECONCILED server
    id (the name the local server answers to today). digit_scorer uses
    the deeper scan window so prose-lead-in models still score.
    """
    context = legexec.LegContext(
        model=model,
        model_id=server_model_id(model),
        base_url=base_url,
        personas=[],
        stimuli=stimuli,
        inference=inference_settings(base_url),
    )
    return legexec.make_scorer(context), legexec.make_digit_scorer(context)


def _now_iso() -> str:
    """The current UTC time as an ISO-8601 string (record timestamps)."""
    return datetime.now(timezone.utc).isoformat()


def _call(scorer, messages: list[dict]) -> dict:
    """One scorer call with its wall-clock time; failures become records.

    Never raises: any exception the transport produces is folded into a
    failed result so the record (and its error text) survives.
    """
    started = time.monotonic()
    try:
        raw = scorer(messages)
    except Exception as exc:  # noqa: BLE001 — surfaced on the record
        raw = {
            "succeeded": False,
            "raw_logprob_response": f"{type(exc).__name__}: {exc}",
        }
    return {**raw, "elapsed_seconds": time.monotonic() - started}


def _prompt_sha(system_prompt: str, user_prompt: str) -> str:
    """The audit hash of one prompt pair (house convention: system + US)."""
    return hashlib.sha256(
        (system_prompt + "\x1e" + user_prompt).encode("utf-8")
    ).hexdigest()


def execute_cell(
    context,
    spec,
    stimuli: dict[str, dict],
    cell: tuple,
    scorer,
    digit_scorer,
    run_id: str,
    dataset_sha256: str,
) -> dict:
    """Run one cell end to end and return its record (never raises).

    The cell is (model, persona_id, experiment, arm, blind). Every item
    of the arm gets its own call in survey order; the record carries the
    choice scoring at the top level and every digit item under
    digit_items, plus the provenance stamp (run id, dataset hash,
    persona id and pid, prompt hashes, status ok/failed).
    """
    _model, persona_id, experiment, arm, blind = cell
    blinded = blind == "blinded"
    persona = context.personas[persona_id]
    items = prompts_twin.arm_items(spec, arm, stimuli)
    system = prompts_twin.system_prompt(spec, stimuli, blinded)
    record: dict = {
        "run_id": run_id,
        "model": context.model,
        "model_id": context.model_id,
        "experiment": experiment,
        "arm": arm,
        "blind": blind,
        "persona_id": persona_id,
        "persona_pid": persona.get("pid"),
        "dataset_sha256": dataset_sha256,
        "qids": list(spec.arm_qids(arm)),
        "qid": spec.arm_qids(arm)[0],
        "system_prompt": system,
        "inference": context.inference,
        "timestamp": _now_iso(),
    }
    problems: list[str] = []
    choice: dict | None = None
    digit_entries: list[dict] = []
    for item in items:
        user = prompts_twin.item_user_prompt(persona, spec, arm, item, stimuli)
        messages = [{"role": "system", "content": system},
                    {"role": "user", "content": user}]
        raw = _call(scorer if item["kind"] == "choice" else digit_scorer,
                    messages)
        scored = legexec._score_item(experiment, item, raw) \
            if item["kind"] == "choice" \
            else legexec._score_digit_item(experiment, item, raw)
        succeeded = bool(raw.get("succeeded"))
        entry = {
            "qid": item["qid"],
            "kind": item["kind"],
            "row": item["row"],
            "statement": item["statement"],
            "user_prompt": user,
            "prompt_sha256": _prompt_sha(system, user),
            **scored,
            "succeeded": succeeded,
            "error": None if succeeded else
            str(raw.get("raw_logprob_response") or "call failed"),
            "elapsed_seconds": float(raw["elapsed_seconds"]),
        }
        if item["kind"] == "choice":
            choice = entry
        else:
            digit_entries.append(entry)
        if not succeeded:
            problems.append(str(entry["error"]))
    if choice is not None:
        record.update({
            "choice_qid": choice["qid"],
            "p_raw": choice["p_raw"],
            "p_norm": choice["p_norm"],
            "branch_mass": choice["branch_mass"],
            "low_branch_mass": choice["low_branch_mass"],
            "top_logprobs": choice.get("top_logprobs"),
            "user_prompt": choice["user_prompt"],
            "prompt_sha256": choice["prompt_sha256"],
            "choice_succeeded": choice["succeeded"],
        })
    record["digit_items"] = digit_entries
    record["status"] = "ok" if not problems else "failed"
    record["succeeded"] = not problems
    record["error"] = "; ".join(problems) if problems else None
    return record
