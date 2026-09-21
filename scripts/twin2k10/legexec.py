# This file executes one study cell: it turns a (model, persona,
# experiment, arm, blinding) cell into the exact prompts, scores every
# choice question with the proven R1 first-token logprob scorer, draws
# the K=20 temperature samples for every numeric and multi-row question,
# parses every sample, and stamps the full record the study's schema asks
# for. A cell whose calls fail is still returned as a record — kept,
# flagged succeeded=False, with the error text — so a resumed run never
# re-hides a failure. This module holds no loop and no file writing;
# cells.py owns durability and resume.

import hashlib
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

from logprob_scoring import make_first_token_scorer

from twin2k10 import (
    cells,
    config,
    experiments,
    numerics,
    prompts,
    registry,
    scoring,
)

# One cell of the study grid: (model, persona_id, experiment, arm, blind).
Cell = tuple


@dataclass(frozen=True)
class LegContext:
    """Everything one model's cell transport needs, fixed for the model.

    Fields:
      model      — the short study id (e.g. "gpt-oss-20b");
      model_id   — the manager registry id sent as the request's "model";
      base_url   — the llama-server root the calls go to;
      personas   — the shared persona pool (persona_id indexes this list);
      stimuli    — the shipped survey questions keyed by question id;
      inference  — the pinned inference-settings dict stamped on records.
    """

    model: str
    model_id: str
    base_url: str
    personas: list[dict]
    stimuli: dict[str, dict]
    inference: dict


def inference_settings(base_url: str) -> dict:
    """The pinned inference settings stamped on every record.

    seed is the study's design seed (config.SEED); the HTTP requests
    themselves carry the R1 first-token shape (temperature 1.0,
    max_tokens = scan window, logprobs + top_logprobs = top-k) and the
    numeric-sample shape (temperature 1.0, max_tokens = numeric window),
    both without a request seed so every draw is a fresh sample.
    """
    return {
        "temperature": config.TEMPERATURE,
        "top_k": config.TOP_K,
        "scan_tokens": config.SCAN_TOKENS,
        "numeric_samples_k": config.NUMERIC_SAMPLES_K,
        "numeric_max_tokens": config.NUMERIC_MAX_TOKENS,
        "seed": config.SEED,
        "base_url": base_url,
        "logprob_mode": "first_token",
    }


def make_leg_context(model: str, base_url: str,
                     personas: list[dict]) -> LegContext:
    """One model's frozen cell context: ids, pool, prompts, settings."""
    return LegContext(
        model=model,
        model_id=registry.manager_model_id(model),
        base_url=base_url,
        personas=personas,
        stimuli=experiments.load_stimuli(),
        inference=inference_settings(base_url),
    )


def make_scorer(context: LegContext) -> Callable:
    """The R1 first-token scorer for one model, with its control sequences.

    Built on logprob_scoring.make_first_token_scorer with the study's scan
    window (8), top-k coverage (100) and the model's control-token
    sequences from the registry map (gemma-4-26b-a4b's channel header).
    """
    return make_first_token_scorer(
        context.base_url,
        context.model_id,
        scan_tokens=config.SCAN_TOKENS,
        top_k=config.TOP_K,
        control_sequences=registry.control_sequences(context.model),
    )


def prompt_sha256(system_prompt: str, user_prompt: str) -> str:
    """The audit hash of one prompt pair (house convention: system + US)."""
    return hashlib.sha256(
        (system_prompt + "\x1e" + user_prompt).encode("utf-8")
    ).hexdigest()


def _now_iso() -> str:
    """The current UTC time as an ISO-8601 string (record timestamps)."""
    return datetime.now(timezone.utc).isoformat()


def label_map(stimulus: dict) -> dict[str, str]:
    """What each answer letter showed in the prompt (letter -> option text).

    Mirrors the choice-question rendering in prompts.py; a question with
    no options (numeric and multi-row ones) maps to an empty dict.
    """
    options = stimulus.get("options")
    labels = stimulus.get("labels")
    if not options or not labels:
        return {}
    return dict(zip(labels, options))


def _call_choice(scorer: Callable, messages: list[dict]) -> dict:
    """One first-token scorer call with its wall-clock time.

    Returns the scorer's raw result dict plus elapsed_seconds; anything
    that raises becomes a synthetic failed result instead of killing the
    leg (the failure stays visible on the record).
    """
    started = time.monotonic()
    try:
        raw = scorer(messages)
    except Exception as exc:  # noqa: BLE001 — surfaced on the record below
        raw = {"succeeded": False,
               "raw_logprob_response": f"{type(exc).__name__}: {exc}"}
    return {**raw, "elapsed_seconds": time.monotonic() - started}


def _choice_part(experiment: str, context: LegContext, scorer: Callable,
                 messages: list[dict], arm_qids: tuple[str, ...]) -> dict:
    """The choice-scoring fragment of one record (empty when no choice).

    Scores the arm's choice question with one first-token call and
    scoring.score_labels; a failed call scores as "no letter found",
    which the preflight emptiness check flags.
    """
    choice_qids = [qid for qid in arm_qids
                   if context.stimuli[qid]["response_kind"] == "choice"]
    if not choice_qids:
        return {}
    raw = _call_choice(scorer, messages)
    scored = scoring.score_labels(
        raw.get("top_logprobs") or [],
        experiment,
        decision_position=raw.get("decision_position"),
        skipped_prefix=raw.get("skipped_prefix"),
        skipped_len=raw.get("skipped_len"),
    )
    return {
        "choice_qid": choice_qids[0],
        **scored,
        "choice_succeeded": bool(raw.get("succeeded")),
        "choice_error": (None if raw.get("succeeded")
                         else (raw.get("raw_logprob_response")
                               or "call failed")),
        "choice_elapsed_seconds": float(raw["elapsed_seconds"]),
    }


def _sampled_part(context: LegContext, sampler: Callable,
                  messages: list[dict], arm_qids: tuple[str, ...],
                  kind: str) -> dict:
    """The numeric or multi-row sampling fragment of one record.

    Draws the K temperature samples for the arm's first question of the
    given kind, parses every sample with the kind's parser, and reports
    the parsed values plus the parse-failure count (a parse failure is
    never silent — the preflight stops on it). A multi-row sample counts
    as failed when it is unparseable, ANY of its rows is None, or its
    length differs from the item's row count. A multi-row record also
    carries expected_rows, its item's own row count, so the preflight
    can tell a complete answer from a truncated one.
    """
    qids = [qid for qid in arm_qids
            if context.stimuli[qid]["response_kind"] == kind]
    if not qids:
        return {}
    raw = numerics.samples_payload(sampler(messages))
    parse = (scoring.parse_numeric if kind == "numeric"
             else scoring.parse_multi_numeric)
    values = [parse(text) for text in raw["samples"]]
    expected_rows: int | None = None
    if kind == "numeric":
        failures = sum(1 for value in values if value is None)
    else:
        expected_rows = len(context.stimuli[qids[0]]["rows"])
        failures = sum(
            1 for value in values
            if value is None or any(row is None for row in value)
            or len(value) != expected_rows
        )
    prefix = "numeric" if kind == "numeric" else "multi_numeric"
    part = {
        f"{prefix}_qid": qids[0],
        f"{prefix}_samples": raw["samples"],
        f"{prefix}_values": values,
        f"{prefix}_parse_failures": failures,
        f"{prefix}_calls_failed": raw["calls_failed"],
        f"{prefix}_top_logprobs": raw["first_top_logprobs"],
        f"{prefix}_elapsed_seconds": float(raw["elapsed_seconds"]),
        f"{prefix}_errors": raw["errors"],
    }
    if expected_rows is not None:
        part["expected_rows"] = expected_rows
    return part


def _base_record(context: LegContext, cell: Cell) -> tuple[dict, list[dict]]:
    """The identity-and-prompt head of one record, plus its messages.

    Stamps the run-level fields (model ids, prompts, their hash, the
    arm's question ids, the label map) that every part of the record
    shares, and returns the ready-to-send messages.
    """
    _model, persona_id, experiment, arm, blind = cell
    spec = experiments.EXPERIMENTS[experiment]
    arm_qids = spec.arm_qids(arm)
    persona = context.personas[persona_id]
    system_prompt = prompts.build_system_prompt(experiment, blind == "blinded")
    user_prompt = prompts.build_user_prompt(persona, experiment, arm)
    first_choice = next(
        (context.stimuli[qid] for qid in arm_qids
         if context.stimuli[qid]["response_kind"] == "choice"),
        None,
    )
    record = {
        "model_id": context.model_id,
        "experiment": experiment,
        "arm": arm,
        "blind": blind,
        "qids": list(arm_qids),
        "qid": arm_qids[0],
        "system_prompt": system_prompt,
        "user_prompt": user_prompt,
        "prompt_sha256": prompt_sha256(system_prompt, user_prompt),
        "options_original": (first_choice or {}).get("options"),
        "label_map": label_map(first_choice) if first_choice else {},
        "inference": context.inference,
        "timestamp": _now_iso(),
    }
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    return record, messages


def _audit_top_logprobs(choice: dict, numeric: dict,
                        multi: dict) -> list | None:
    """The canonical top_logprobs audit list for one record.

    A choice question's decision-position top-k wins; an arm without one
    contributes its first sample's first-token top-k, the same field
    shape every preflight record is judged on. None when the arm had no
    calls at all (never the case in practice).
    """
    if choice:
        return choice.get("top_logprobs")
    part = numeric or multi
    if part:
        key = "numeric_top_logprobs" if numeric else "multi_numeric_top_logprobs"
        return part[key]
    return None


def _stamp_status(record: dict, choice: dict, numeric: dict,
                  multi: dict) -> None:
    """Stamp the record's footer: parse failures, success flag, error text.

    succeeded is True only when every call behind the record succeeded
    AND every sample parsed cleanly — a record with any unparseable row
    must never claim success. Failures surface as the kept record's
    error text so a resumed run never re-hides them.
    """
    choice_failed = 1 if (choice and not choice.get("choice_succeeded")) else 0
    calls_failed = (
        choice_failed
        + numeric.get("numeric_calls_failed", 0)
        + multi.get("multi_numeric_calls_failed", 0)
    )
    parse_failed = (
        numeric.get("numeric_parse_failures", 0)
        + multi.get("multi_numeric_parse_failures", 0)
    )
    problems: list[str] = []
    if choice and choice.get("choice_error"):
        problems.append(str(choice["choice_error"]))
    problems.extend(numeric.get("numeric_errors") or [])
    problems.extend(multi.get("multi_numeric_errors") or [])
    record["parse_failures"] = parse_failed
    record["succeeded"] = calls_failed == 0 and parse_failed == 0
    detail = "; ".join(problems)
    if not detail and parse_failed:
        detail = f"{parse_failed} sample(s) failed to parse"
    record["error"] = None if record["succeeded"] else (
        detail or f"{calls_failed} call(s) failed"
    )


def execute_cell(context: LegContext, scorer: Callable, sampler: Callable,
                 cell: Cell) -> dict:
    """Run one cell end to end and return its record (never raises).

    Builds the prompts once, scores the arm's choice question with one
    first-token call, draws the K numeric samples (numeric and multi-row
    questions each), and stamps everything on one record. succeeded is
    True only when every call behind the record succeeded; failures keep
    their row with the error text so a resumed run never re-hides them.
    """
    experiment = cell[2]
    arm_qids = experiments.EXPERIMENTS[experiment].arm_qids(cell[3])
    record, messages = _base_record(context, cell)
    choice = _choice_part(experiment, context, scorer, messages, arm_qids)
    numeric = _sampled_part(context, sampler, messages, arm_qids, "numeric")
    multi = _sampled_part(context, sampler, messages, arm_qids,
                          "multi_numeric")
    record.update(choice)
    record.update(numeric)
    record.update(multi)
    audit = _audit_top_logprobs(choice, numeric, multi)
    if audit is not None:
        record["top_logprobs"] = audit
    _stamp_status(record, choice, numeric, multi)
    return record


def make_transport(context: LegContext, on_record: Callable[[dict], None],
                   scorer: Callable | None = None,
                   sampler: Callable | None = None) -> Callable:
    """The cells.run_cells transport for one model: execute + notify.

    on_record fires after each cell's record exists (the runner uses it
    for progress counting); it never influences the record itself.
    scorer / sampler override the model's real HTTP callables (offline
    tests inject fakes here — the same injectable-transport pattern as
    the R1 code).
    """
    scorer = scorer if scorer is not None else make_scorer(context)
    sampler = sampler if sampler is not None else numerics.make_numeric_sampler(
        context.base_url, context.model_id
    )

    def transport(cell: Cell) -> dict:
        record = execute_cell(context, scorer, sampler, cell)
        on_record(record)
        return record

    return transport


def leg_cells(model: str, persona_ids: list[int],
              experiment: str, blind: str) -> list[Cell]:
    """One leg's cells in pinned order: persona, then arm in registry order.

    Built with cells.enumerate_cells (single experiment map, single
    blinding filter) so a leg's cell list is the study's own enumeration.
    """
    planned = cells.enumerate_cells(
        models=[model],
        personas=persona_ids,
        experiments_map={experiment: experiments.EXPERIMENTS[experiment]},
    )
    return [cell for cell in planned if cell[4] == blind]


def leg_dir(run_root, model: str, experiment: str, blind: str):
    """One leg's directory: <root>/<safe_model>/<experiment>_<blind>."""
    from pathlib import Path

    return Path(run_root) / registry.safe_model_name(model) / \
        f"{experiment}_{blind}"
