"""Runner for the three-game experiment: plans, calls, saves, resumes.

What this file does, in plain language:

- ``build_plan`` turns a config (YAML file or CLI flags) into the exact
  list of samples to collect: one entry per (game, variant, arm, model,
  persona, draw), with a stable idempotency key so a restarted run never
  duplicates a sample that already succeeded.
- ``count_samples`` counts the plan without running anything
  (``--print-counts`` prints per-cell and total counts).
- ``run_plan`` walks the plan cell by cell, builds each prompt, rolls
  the private die where needed, assigns matrix roles in a seed-fixed
  balanced alternation, sends the request at temperature 1.0 through the
  configured route (retries 429/5xx/timeouts with capped backoff),
  parses the answer, detects truncated completions, records tokens and
  cost, and appends every finished record to a per-cell JSONL file
  immediately (a crash never loses finished records).
- ``main`` is the command-line entry point.  No spending caps and no
  cost-based stopping exist anywhere here: the run goes to the frozen
  sample counts, nothing else.

No paid API calls happen unless you run this file yourself with real
credentials in the environment.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Callable

try:  # works both as a package module and run from the scripts directory
    from sixgame.data_root import DataRootError, resolve_out_dir
    from sixgame.games import variant_spec
    from sixgame.preflight import run_preflight
    from sixgame.route_check import write_route_report
    from sixgame.probes import code_recognition, probe_prompt
    from sixgame.transport import (
        DRY_CAPTURED,
        LIVE_CAPTURED,
        MeslUnavailableError,
        TransportError,
        TransportTimeout,
        call_with_retry,
        route_for,
    )
except ImportError:  # pragma: no cover - direct execution layout
    from data_root import DataRootError, resolve_out_dir
    from games import (
        variant_spec,
    )
    from preflight import run_preflight
    from route_check import write_route_report
    from probes import code_recognition, probe_prompt
    from transport import (
        DRY_CAPTURED,
        LIVE_CAPTURED,
        MeslUnavailableError,
        TransportError,
        TransportTimeout,
        call_with_retry,
        route_for,
    )

TEMPERATURE = 1.0

#: finish_reason values that mean the output was cut off (never done on
#: purpose here — max_tokens is >= 32768 headroom; detection only).
_TRUNCATED_FINISH = {"length", "incomplete", "MAX_TOKENS"}

_MODELS = [
    "deepseek-v4-flash",
    "anthropic/claude-sonnet-5",
    "openai/gpt-5.6-luna",
]


# Plan/config logic lives in plan.py; re-exported here so callers can
# use runner.build_plan and friends unchanged.
try:
    from sixgame.plan import (  # noqa: F401
        Sample,
        assign_role,
        build_plan,
        cells,
        default_config,
        draw_true_roll,
        load_config,
        load_persona_names,
        personas_for_cell,
        print_counts,
        probe_plan,
    )
except ImportError:  # pragma: no cover
    from plan import (  # noqa: F401
        Sample,
        assign_role,
        build_plan,
        cells,
        default_config,
        draw_true_roll,
        load_config,
        load_persona_names,
        personas_for_cell,
        print_counts,
        probe_plan,
    )


def persona_text_for(sample: Sample, personas_dir: Path) -> str | None:
    """The persona text a sample's prompt should embed.

    ONLY the persona arm gets the persona file's text.  The no_persona
    arm always gets None (the name-only placebo) — bug A1 in
    RESULT-2723 showed that loading the text regardless of arm broke
    the arm contrast.
    """
    if sample.arm != "persona":
        return None
    persona_file = personas_dir / f"{sample.persona_id}.txt"
    if not persona_file.exists():
        return None
    return persona_file.read_text(encoding="utf-8")


def build_decision_prompt(
    sample: Sample, persona_text: str | None, roll: int | None, seed: int
) -> str:
    """Build the decision prompt for one sample."""
    from games import die_roll_prompt, eleven_twenty_prompt, matrix_prompt

    if sample.game == "1120":
        return eleven_twenty_prompt(sample.variant, sample.persona_id, persona_text)
    if sample.game == "dieroll":
        return die_roll_prompt(
            sample.variant, int(roll or 1), sample.persona_id, persona_text
        )
    base_game = "G4" if sample.variant == "G4" else "G1"
    matrix_variant = "relabel" if sample.variant == "relabel" else "base"
    return matrix_prompt(
        base_game, matrix_variant, sample.role or "Row", sample.persona_id, persona_text
    )


def matrix_base_game(variant: str) -> str:
    """The PMS base matrix a variant plays on ('relabel' mirrors G1)."""
    return "G4" if variant == "G4" else "G1"


def prompt_hash(prompt: str) -> str:
    """A short hash of the prompt text, logged on every record."""
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:16]


def parse_answer(
    raw_content: str | None, parse_key: str, legal: tuple
) -> tuple[object | None, str]:
    """Extract (choice, reason) from a raw completion, or (None, ...).

    Finds the first '{' to last '}' and parses that as JSON; the choice
    must be inside the legal action set or it counts as a parse failure.
    """
    if not raw_content:
        return None, ""
    start = raw_content.find("{")
    end = raw_content.rfind("}")
    if start == -1 or end <= start:
        return None, ""
    try:
        obj = json.loads(raw_content[start : end + 1])
    except (json.JSONDecodeError, ValueError):
        return None, ""
    if not isinstance(obj, dict):
        return None, ""
    choice = obj.get(parse_key)
    if isinstance(choice, str):
        choice = choice.strip()
        if parse_key == "action":
            choice = choice.upper()
        try:
            choice = int(choice)
        except (TypeError, ValueError):
            pass
    if isinstance(choice, str) is False and not isinstance(choice, int):
        choice = None
    if choice is not None and choice not in legal:
        choice = None
    reason = obj.get("reason")
    return choice, (reason if isinstance(reason, str) else "")


def truncated(finish_reason: str | None) -> bool:
    """True when the finish reason says the output was cut off."""
    return finish_reason in _TRUNCATED_FINISH


def cost_usd(
    model: str, prompt_tokens: int | None, completion_tokens: int | None, prices: dict
) -> float | None:
    """The recorded cost of one call from per-model price config (reporting
    only — never used for stopping)."""
    price = prices.get(model)
    if price is None or prompt_tokens is None or completion_tokens is None:
        return None
    return prompt_tokens / 1e6 * price.get(
        "prompt_per_mtok", 0.0
    ) + completion_tokens / 1e6 * price.get("completion_per_mtok", 0.0)


def record_for(
    sample: Sample,
    prompt: str,
    response: dict | None,
    error: str | None,
    route: str,
    elapsed: float,
    prices: dict,
) -> dict:
    """Build one JSONL record from a finished (or failed) call."""
    key = sample.idempotency_key(prompt_hash(prompt), route)
    record = {
        "game": sample.game,
        "variant": sample.variant,
        "arm": sample.arm,
        "model": sample.model,
        "route": route,
        "persona_id": sample.persona_id,
        "draw_id": sample.draw_id,
        "role": sample.role,
        "namespace": sample.namespace,
        "choice": None,
        "reason": "",
        "raw_content": None,
        "finish_reason": None,
        "truncated": False,
        "temperature": TEMPERATURE,
        "prompt_hash": prompt_hash(prompt),
        "idempotency_key": key,
        "timestamp": "",
        "cache_status": "MISS",
        "cache_kind": "none",  # "context" | "response" | "none"
        "model_dated": None,
        "prompt_tokens": None,
        "completion_tokens": None,
        "reasoning_tokens": None,
        "cost_usd": None,
        "elapsed_seconds": round(elapsed, 3),
        "succeeded": False,
        "error": error,
    }
    if response is None:
        return record
    from datetime import datetime, timezone

    record["timestamp"] = datetime.now(timezone.utc).isoformat()
    try:
        choice0 = response["choices"][0]
        message = choice0["message"]
        raw_content = message.get("content")
        finish = choice0.get("finish_reason")
        if sample.namespace == "probes":
            value, reason = parse_probe_answer(raw_content)
            record["recognition"] = code_recognition(raw_content)
        else:
            spec = variant_spec(sample.game, sample.variant)
            value, reason = parse_answer(raw_content, spec.parse_key, spec.actions)
        usage = response.get("usage", {})
        details = usage.get("completion_tokens_details", {}) or {}
        cache_status, cache_kind = classify_cache(usage)
        record["cache_kind"] = cache_kind
        record.update(
            {
                "choice": value,
                "reason": reason,
                "raw_content": raw_content,
                "finish_reason": finish,
                "truncated": truncated(finish),
                "cache_status": cache_status,
                "model_dated": response.get("model"),
                "prompt_tokens": usage.get("prompt_tokens"),
                "completion_tokens": usage.get("completion_tokens"),
                "reasoning_tokens": details.get("reasoning_tokens"),
                "cost_usd": cost_usd(
                    sample.model,
                    usage.get("prompt_tokens"),
                    usage.get("completion_tokens"),
                    prices,
                ),
                "succeeded": value is not None and not truncated(finish),
            }
        )
    except (KeyError, IndexError, TypeError, AttributeError) as exc:
        record["error"] = str(exc)
    return record


def parse_probe_answer(raw_content: str | None) -> tuple[str | None, str]:
    """Extract (answer_text, reason) from a probe's free-text JSON.

    Probes answer {"recognised": ..., "answer": ...}; the answer is
    free text, so the choice field carries the answer string itself
    (bug A2 in RESULT-2723: probes previously recorded choice=None and
    succeeded=False even for perfectly parseable answers).
    """
    if not raw_content:
        return None, ""
    start = raw_content.find("{")
    end = raw_content.rfind("}")
    if start == -1 or end <= start:
        return None, ""
    try:
        obj = json.loads(raw_content[start : end + 1])
    except (json.JSONDecodeError, ValueError):
        return None, ""
    if not isinstance(obj, dict):
        return None, ""
    answer = obj.get("answer")
    if not isinstance(answer, str) or not answer.strip():
        return None, ""
    return answer, ("yes" if obj.get("recognised") else "no")


def classify_cache(usage: dict) -> tuple[str, str]:
    """Classify one response's caching as (cache_status, cache_kind).

    Rule change per ANALYSIS_PLAN: provider context/prompt-prefix
    caching (DeepSeek automatic context caching, reported as
    prompt_cache_hit_tokens) means the completion was still freshly
    sampled and is NOT an exclusion.  Only a gateway response cache —
    a reused completion body — counts as a response cache and is
    excluded downstream in analysis.apply_exclusions.
    """
    if usage.get("response_cache_hit") or usage.get("cached_completion"):
        return "HIT", "response"
    if usage.get("prompt_cache_hit_tokens"):
        return "HIT", "context"
    return "MISS", "none"


def cell_path(out_dir: Path, sample: Sample) -> Path:
    """The per-cell JSONL file for one sample's cell and namespace."""
    slug = sample.model.replace("/", "_")
    name = (
        f"{sample.namespace}_{sample.game}_{sample.variant}_{sample.arm}_{slug}.jsonl"
    )
    return out_dir / name


def read_idempotency_keys(path: Path) -> set[str]:
    """All idempotency keys already in a JSONL file (empty if missing)."""
    if not path.exists():
        return set()
    keys = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            keys.add(json.loads(line).get("idempotency_key"))
        except json.JSONDecodeError:
            continue  # a torn last line after a crash is skipped, not fatal
    keys.discard(None)
    return keys


def append_record(path: Path, record: dict) -> None:
    """Append one record to the per-cell JSONL immediately (crash-safe)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def run_sample(
    sample: Sample,
    persona_text: str | None,
    roll: int | None,
    seed: int,
    prices: dict,
    route_map: dict[str, str] | None,
    sleep: Callable[[float], None] = (lambda _s: None),
) -> tuple[dict, str]:
    """Run one API call and return (record, prompt). Never raises."""
    prompt = build_decision_prompt(sample, persona_text, roll, seed)
    if sample.namespace == "probes":
        prompt = probe_prompt(
            sample.game, sample.variant, sample.persona_id, persona_text
        )
    route = route_for(sample.model, route_map)
    payload = {
        "model": sample.model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": TEMPERATURE,
    }
    start = __import__("time").perf_counter()
    try:
        response = call_with_retry(payload, sample.model, route, sleep)
        body = response.body
        elapsed = __import__("time").perf_counter() - start
        return record_for(sample, prompt, body, None, route, elapsed, prices), prompt
    except (TransportError, TransportTimeout) as exc:
        elapsed = __import__("time").perf_counter() - start
        return record_for(
            sample, prompt, None, str(exc), route, elapsed, prices
        ), prompt


def run_plan(
    plan: list[Sample],
    personas_dir: Path,
    out_dir: Path,
    prices: dict,
    route_map: dict[str, str] | None = None,
    seed: int = 0,
    sleep: Callable[[float], None] = (lambda _s: None),
    log: Callable[[str], None] = print,
) -> dict:
    """Run a whole plan, resuming without duplicating finished samples."""
    out_dir.mkdir(parents=True, exist_ok=True)
    done = 0
    skipped = 0
    failed = 0
    for sample in plan:
        path = cell_path(out_dir, sample)
        existing = read_idempotency_keys(path)
        route = route_for(sample.model, route_map)
        roll = draw_true_roll(
            seed,
            sample.game,
            sample.variant,
            sample.arm,
            sample.model,
            sample.persona_id,
            sample.draw_id,
        )
        persona_text = persona_text_for(sample, personas_dir)
        prompt = build_decision_prompt(sample, persona_text, roll, seed)
        if sample.namespace == "probes":
            prompt = probe_prompt(
                sample.game, sample.variant, sample.persona_id, persona_text
            )
        key = sample.idempotency_key(prompt_hash(prompt), route)
        if key in existing:
            skipped += 1
            continue
        record, _ = run_sample(
            sample, persona_text, roll, seed, prices, route_map, sleep
        )
        append_record(path, record)
        if record["succeeded"]:
            done += 1
        elif record["error"]:
            failed += 1
        log(
            f"{sample.game}/{sample.variant}/{sample.arm} "
            f"{sample.persona_id}#{sample.draw_id} -> "
            f"{record['choice'] if record['succeeded'] else record['error']}"
        )
    return {"completed": done, "skipped": skipped, "failed": failed}


def main(argv: list[str] | None = None) -> int:
    """CLI entry point (see module docstring). --print-counts makes no calls."""
    parser = argparse.ArgumentParser(description="sixgame experiment runner")
    parser.add_argument("--config", help="config YAML (else built-in scope)")
    parser.add_argument(
        "--scope", choices=["engineering", "full"], default="engineering"
    )
    parser.add_argument("--game")
    parser.add_argument("--variant")
    parser.add_argument("--arm")
    parser.add_argument("--model")
    parser.add_argument("--personas", type=int, default=5)
    parser.add_argument("--draws", type=int, default=10)
    parser.add_argument("--seed", type=int, default=20261016)
    parser.add_argument(
        "--run-id",
        default="engineering_pilot_corrective",
        help="run folder name under the data root (default output location)",
    )
    parser.add_argument(
        "--out-dir",
        default=None,
        help="output folder; must live under the data root unless "
        "--allow-any-outdir is given (default: <data-root>/<run-id>)",
    )
    parser.add_argument(
        "--allow-any-outdir",
        action="store_true",
        help="allow --out-dir outside the data root (tests only)",
    )
    parser.add_argument("--personas-csv", default="final_200_personas.csv")
    parser.add_argument(
        "--personas-dir",
        default=".",
        help="directory holding <persona_id>.txt files (default: cwd)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="run only the first N planned samples (validation slices)",
    )
    parser.add_argument(
        "--skip-preflight",
        action="store_true",
        help="skip the mandatory pre-execution validation gate (tests only)",
    )
    parser.add_argument(
        "--dry-transport",
        action="store_true",
        help="run the full plan against an offline mock transport and "
        "capture every serialized request body (no network, no cost)",
    )
    parser.add_argument("--print-counts", action="store_true")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print the first prompt per cell, no calls",
    )
    parser.add_argument(
        "--check-route",
        action="store_true",
        help="run the non-billable MESL route and Cloudflare auth "
        "checks, save evidence under the data root, and exit (no "
        "model calls). Re-runnable before a batch launch.",
    )
    args = parser.parse_args(argv)

    if args.check_route:
        try:
            from sixgame.data_root import default_data_root
        except ImportError:
            from data_root import default_data_root
        report = write_route_report(default_data_root())
        print(json.dumps(report, default=str))
        if not report["mesl_ok"]:
            print(
                "ROUTE CHECK FAIL: MESL proxy unusable — Claude/GPT "
                "calls are refused until this is fixed",
                file=sys.stderr,
            )
            return 2
        return 0

    config = (
        load_config(Path(args.config)) if args.config else default_config(args.scope)
    )
    if args.personas != 5 or args.draws != 10:
        config["personas"] = args.personas
        config["draws_per_cell"] = args.draws
    if args.game and args.variant:
        config["games"] = {args.game: {"variants": [args.variant]}}
    # Narrow the config to the CLI filters so the preflight gate's
    # expected counts match the filtered plan actually being run.
    if args.model:
        config["models"] = [m for m in config["models"] if m == args.model]
    if args.game:
        config["games"] = {g: v for g, v in config["games"].items() if g == args.game}
    if args.variant:
        for g, v in config["games"].items():
            v["variants"] = [x for x in v["variants"] if x == args.variant]
    if args.arm:
        config["arms"] = [a for a in config["arms"] if a == args.arm]

    if args.print_counts:
        print(print_counts(config))
        return 0
    try:
        out_dir = resolve_out_dir(
            args.out_dir, args.run_id, allow_any=args.allow_any_outdir
        )
    except DataRootError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    persona_names = load_persona_names(Path(args.personas_csv), config["personas"])
    if not persona_names:
        print("no personas found", file=sys.stderr)
        return 1
    plan = build_plan(
        config,
        persona_names,
        args.seed,
        game_filter=args.game,
        variant_filter=args.variant,
        arm_filter=args.arm,
        model_filter=args.model,
    )
    plan = plan + probe_plan(
        config,
        persona_names,
        args.seed,
        game_filter=args.game,
        variant_filter=args.variant,
        arm_filter=args.arm,
        model_filter=args.model,
    )
    if args.dry_run:
        sample = plan[0]
        roll = draw_true_roll(
            args.seed,
            sample.game,
            sample.variant,
            sample.arm,
            sample.model,
            sample.persona_id,
            sample.draw_id,
        )
        print(build_decision_prompt(sample, None, roll, args.seed))
        return 0
    if args.limit is not None:
        plan = plan[: args.limit]
    route_map = config.get("route_map")
    if args.dry_transport:
        # Offline validation run: every model goes through the mock, and
        # the captured request bodies double as the preflight evidence.
        route_map = {model: "dry" for model in config["models"]}
    if not args.skip_preflight:
        failures = run_preflight(
            plan, Path(args.personas_dir), config, args.seed, plan_limit=args.limit
        )
        if failures:
            for failure in failures:
                print(f"PREFLIGHT FAIL: {failure}", file=sys.stderr)
            print(
                f"preflight gate: {len(failures)} failure(s) — run refused",
                file=sys.stderr,
            )
            return 2
    prices = config.get("prices", {})
    try:
        summary = run_plan(
            plan,
            Path(args.personas_dir),
            out_dir,
            prices,
            route_map,
            args.seed,
        )
    except MeslUnavailableError as exc:
        # Fail-closed refusal (task 2767): no Claude/GPT call was made,
        # no direct fallback exists. Stop the whole run with a reason.
        print(f"ROUTE REFUSED: {exc}", file=sys.stderr)
        return 4
    if args.dry_transport:
        captured_path = out_dir / "captured_requests.jsonl"
        captured_path.parent.mkdir(parents=True, exist_ok=True)
        with captured_path.open("w", encoding="utf-8") as fh:
            for payload in DRY_CAPTURED:
                fh.write(json.dumps(payload, ensure_ascii=False) + "\n")
        if not args.skip_preflight:
            post = run_preflight(
                plan,
                Path(args.personas_dir),
                config,
                args.seed,
                captured=DRY_CAPTURED,
                plan_limit=args.limit,
            )
            if post:
                for failure in post:
                    print(f"DRY-RUN MISMATCH: {failure}", file=sys.stderr)
                return 3
            print(
                f"dry-run: {len(DRY_CAPTURED)} captured requests match the "
                "planned prompts"
            )
    if LIVE_CAPTURED and not args.dry_transport:
        # Live-run evidence (task 2739): save the exact serialized request
        # bodies the direct DeepSeek route sent, for post-run verification.
        captured_path = out_dir / "captured_requests.jsonl"
        captured_path.parent.mkdir(parents=True, exist_ok=True)
        with captured_path.open("w", encoding="utf-8") as fh:
            for payload in LIVE_CAPTURED:
                fh.write(json.dumps(payload, ensure_ascii=False) + "\n")
    print(json.dumps(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
