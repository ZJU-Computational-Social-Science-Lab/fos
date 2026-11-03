# This file is the parity check the launch gate demands: it replays ONE
# archived production record's exact prompt against the SAME model on the
# restored port-8080 llama-server and compares the first-token top-1 with
# the top-1 stored in the archive. If the restored serving path
# reproduces the archived answer token, the new run's records are
# compatible with the frozen runs' analysis. Functions:
#   replay_record — one archived record's prompt -> fresh top-k evidence.
#   top_tokens    — the readable token list of a top-k entry list.
from __future__ import annotations

from twin2k10r.integration.production.model_ids import server_model_id


class ParityMismatchError(RuntimeError):
    """The replayed top-1 token differs from the archived record's."""


def top_tokens(top_logprobs, count: int = 5) -> list[str]:
    """The first `count` token texts of a top-k list (readable evidence)."""
    tokens = []
    for entry in top_logprobs or []:
        if isinstance(entry, dict) and isinstance(entry.get("token"), str):
            tokens.append(entry["token"])
        if len(tokens) >= count:
            break
    return tokens


def replay_record(model: str, base_url: str, record: dict) -> dict:
    """Replay one archived record's prompt; compare the top-1 token.

    The record carries its own system/user prompts and its stored
    decision-position top-k. The fresh call uses the frozen first-token
    request shape (scan window 8, top_k 100, temperature 1.0). Returns
    the evidence dict; raises ParityMismatchError when the top-1 differs
    or the fresh call failed — the launch gate must stop on that.
    """
    from logprob_scoring import make_first_token_scorer

    scorer = make_first_token_scorer(
        base_url, server_model_id(model), scan_tokens=8, top_k=100)
    raw = scorer([
        {"role": "system", "content": record["system_prompt"]},
        {"role": "user", "content": record["user_prompt"]},
    ])
    if not raw.get("succeeded"):
        raise ParityMismatchError(
            f"replay call failed: "
            f"{str(raw.get('raw_logprob_response'))[:200]}")
    stored_top1 = (record.get("top_logprobs") or [{}])[0]
    fresh = raw.get("top_logprobs") or []
    fresh_top1 = fresh[0] if fresh else {}
    evidence = {
        "model": model,
        "experiment": record.get("experiment"),
        "stored_top1": stored_top1.get("token"),
        "fresh_top1": fresh_top1.get("token"),
        "stored_top5": top_tokens(record.get("top_logprobs")),
        "fresh_top5": top_tokens(fresh),
        "match": (stored_top1.get("token") is not None
                  and stored_top1.get("token") == fresh_top1.get("token")),
    }
    if not evidence["match"]:
        raise ParityMismatchError(
            f"parity replay MISMATCH for {model}: stored top-1 "
            f"{evidence['stored_top1']!r} but fresh top-1 "
            f"{evidence['fresh_top1']!r}")
    return evidence


def load_archived_record(path, index: int = 0) -> dict:
    """One archived record (by line index) from a records.jsonl file."""
    lines = [line for line in
             open(path, encoding="utf-8").read().splitlines()
             if line.strip()]
    if index >= len(lines):
        raise IndexError(
            f"record {index} not in {path} ({len(lines)} records)")
    return __import__("json").loads(lines[index])
