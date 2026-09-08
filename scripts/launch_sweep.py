#!/usr/bin/env python3
"""Sweep-leg machinery for the study's launch wrapper: legs, watchdog, smoke.

The launch layer around the Gui & Toubia replication sweep is split into
scripts that never change what the study's existing tools do: launch_grid.py
(flags, plan, run order), launch_support.py (model-manager calls and
persona-pool generation/subsampling), launch_manifest.py (the run-level
manifest and its resume merge), and launch_sweep.py (this module: the
concurrent (depth x blinding) sweep legs through the sweep tool's own
helpers, the health watchdog, and the smoke pre-flight). A leg's records
are written only when the whole leg completes, so the unit of resume is
the (depth x blinding) leg - launch_manifest reads finished legs back from
their own files when a run is resumed. Importing this module never opens
a socket.

Function map: _leg_dir/_leg_is_done (output dir + resume check), _make_chat
(counting chat wrapper with progress + abort), _run_one_leg/_save_leg_outputs
(one leg: run the sweep, then write its records/manifest), _watchdog (abort
the run when the chat server dies), _progress_line (live progress text), and
the smoke pre-flight _smoke with its helpers _smoke_direct_chat,
_draw_smoke_persona, _run_smoke_purchase, _write_smoke_manifest,
_report_smoke.
"""

from __future__ import annotations

import json
import sys
import threading
import time
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPT_DIR = _REPO_ROOT / "scripts"
_SRC = _REPO_ROOT / "src"
for _dir in (_SCRIPT_DIR, _SRC):
    if str(_dir) not in sys.path:
        sys.path.insert(0, str(_dir))

from fos.experiments.sweep_kit import (  # noqa: E402
    parse_purchase,
    run_persona_sweep,
    run_sweep,
    write_manifest,
)
from launch_support import (  # noqa: E402
    Settings,
    _SWEEP,
    _load_model,
    _manager_status,
    _now,
    _post_json,
    _repo_sha,
)

HEALTH_POLL_SECONDS = 20.0
HEALTH_MISSES_ABORT = 4


def _leg_dir(run_dir: Path, leg: dict[str, str]) -> Path:
    """The output directory of one (depth x blinding) leg."""
    return run_dir / f"{leg['depth']}_{leg['blinding']}"


def _leg_is_done(run_dir: Path, safe_model: str, leg: dict[str, str]) -> bool:
    """Resume check: does this leg already have files and a manifest?"""
    leg_dir = _leg_dir(run_dir, leg)
    jsonl = leg_dir / f"{safe_model}_{leg['blinding']}.jsonl"
    csv = leg_dir / f"{safe_model}_{leg['blinding']}.csv"
    return (
        jsonl.exists()
        and jsonl.stat().st_size > 0
        and csv.exists()
        and (leg_dir / "manifest.json").exists()
    )


def _make_chat(
    settings: Settings,
    total_calls: int,
    progress: Callable[[int, int, int, float], None],
) -> tuple[Callable[..., str], dict[str, int], threading.Event]:
    """Counting chat wrapper shared by all legs (progress + abort flag).

    state counts calls made and calls whose answer parsed; every
    progress_every-th call prints a live line; once abort is set every new
    call raises so the legs stop immediately.
    """
    state = {"done": 0, "parsed": 0}
    abort = threading.Event()
    lock = threading.Lock()
    started = time.monotonic()
    inner = _SWEEP.build_sweep_chat_fn(settings.base_url, settings.model, 16, 120.0)

    def chat_fn(messages: list[dict[str, str]], temperature: float) -> str:
        if abort.is_set():
            raise RuntimeError(
                "chat server lost; run aborted (check the "
                "model manager and rerun with --resume)"
            )
        raw = inner(messages, temperature)
        with lock:
            state["done"] += 1
            if raw and parse_purchase(raw) is not None:
                state["parsed"] += 1
            done, parsed = state["done"], state["parsed"]
        if done % settings.progress_every == 0:
            progress(
                done, total_calls, parsed, done / max(1e-9, time.monotonic() - started)
            )
        return raw

    return chat_fn, state, abort


def _run_one_leg(
    settings: Settings,
    plan: dict[str, Any],
    products: list[dict[str, Any]],
    personas_by_product: dict[str, Any] | None,
    run_dir: Path,
    chat_fn: Callable[..., str],
    leg: dict[str, str],
    results: list[dict[str, Any]],
    log: Callable[[str], None],
) -> None:
    """Run one (depth x blinding) leg and record its outcome.

    The leg reuses the sweep tool's own helpers unchanged (same design,
    prompts, record writer and manifest layout). Its output directory is
    <run>/<depth>_<blinding>/ so legs never collide while they run
    concurrently.
    """
    leg_dir = _leg_dir(run_dir, leg)
    leg_dir.mkdir(parents=True, exist_ok=True)
    design = _SWEEP._build_design(
        plan["levels"],
        [leg["blinding"]],
        settings.seed,
        list(_SWEEP.COVARIATE_KINDS),
        leg["depth"],
    )
    try:
        if leg["depth"] == "none":
            records = run_sweep(
                design,
                products,
                settings.model,
                chat_fn,
                draws=settings.draws,
                blinding=leg["blinding"],
                seed=settings.seed,
                persona_depth="none",
            )
        else:
            if personas_by_product is None:
                raise RuntimeError("persona leg without persona pools")
            records, _skipped = run_persona_sweep(
                design,
                personas_by_product,
                settings.model,
                chat_fn,
                blinding=leg["blinding"],
                persona_depth=leg["depth"],
                seed=settings.seed,
            )
    except Exception as exc:  # never swallow a leg failure
        results.append({**leg, "ok": False, "error": f"{exc}"})
        log(f"leg {leg['depth']}_{leg['blinding']} FAILED: {exc}")
        return
    if not records:
        results.append({**leg, "ok": False, "error": "no records produced"})
        log(f"leg {leg['depth']}_{leg['blinding']} produced no records")
        return
    _save_leg_outputs(
        settings,
        plan,
        leg_dir,
        design,
        leg,
        records,
        products,
        run_dir.name,
        results,
        log,
    )


def _save_leg_outputs(
    settings: Settings,
    plan: dict[str, Any],
    leg_dir: Path,
    design: Any,
    leg: dict[str, str],
    records: list[dict[str, Any]],
    products: list[dict[str, Any]],
    run_name: str,
    results: list[dict[str, Any]],
    log: Callable[[str], None],
) -> None:
    """Write one completed leg's records, manifest and result summary."""
    safe_model = _SWEEP._safe_model_name(settings.model)
    base = leg_dir / f"{safe_model}_{leg['blinding']}"
    _SWEEP._write_records(base, records)
    parsed = sum(1 for record in records if record.get("succeeded"))
    mean_elapsed = sum(
        float(record.get("elapsed_seconds") or 0.0) for record in records
    ) / len(records)
    write_manifest(
        leg_dir / "manifest.json",
        design,
        settings.model,
        settings.draws,
        leg["blinding"],
        products,
        settings.base_url,
        extra={
            "levels": plan["levels"],
            "temperature": 1.0,
            "seed": settings.seed,
            "argv": list(sys.argv),
            "started": _now(),
            "finished": _now(),
            "depth": leg["depth"],
            "run_name": run_name,
            "personas_per_product": plan["k"] if leg["depth"] != "none" else None,
            "pool_seed": settings.pool_seed,
            "commit_sha": _repo_sha(),
        },
    )
    results.append(
        {
            **leg,
            "ok": True,
            "records": len(records),
            "parsed": parsed,
            "parse_rate": parsed / len(records),
            "mean_elapsed": mean_elapsed,
            "files": [f"{base}.jsonl", f"{base}.csv", str(leg_dir / "manifest.json")],
        }
    )
    log(
        f"leg {leg['depth']}_{leg['blinding']} done: {len(records):,} "
        f"records, parse {100.0 * parsed / len(records):.1f}%"
    )


def _watchdog(
    settings: Settings,
    abort: threading.Event,
    done_event: threading.Event,
    log: Callable[[str], None],
) -> None:
    """Abort the run when the chat server stops answering.

    A manager switch by another session (the known pilot risk) kills the
    llama-server mid-run; without this guard every remaining call would
    retry once and record a silent failure. After HEALTH_MISSES_ABORT
    consecutive failed polls the event trips and the counting chat wrapper
    raises so every leg stops.
    """
    misses = 0
    while not done_event.is_set():
        time.sleep(HEALTH_POLL_SECONDS)
        try:
            with urllib.request.urlopen(
                f"{settings.base_url}/health", timeout=5.0
            ) as reply:
                healthy = reply.status == 200
        except OSError:
            healthy = False
        if healthy:
            misses = 0
            continue
        misses += 1
        log(
            f"warning: {settings.base_url}/health unreachable "
            f"({misses}/{HEALTH_MISSES_ABORT})"
        )
        if misses >= HEALTH_MISSES_ABORT:
            log("aborting: chat server appears to have died (external model switch?)")
            abort.set()
            return


def _progress_line(done: int, total: int, parsed: int, rate: float) -> str:
    """One live progress line: done/total, parse rate so far, ETA."""
    remaining = max(1, total - done)
    return (
        f"progress {done:,}/{total:,} calls "
        f"({100.0 * done / total:.1f}%), parse "
        f"{100.0 * parsed / max(done, 1):.1f}% so far, "
        f"ETA ~{remaining / max(rate, 1e-9) / 3600.0:.1f} h"
    )


def _smoke(settings: Settings, products_path: Path, out: Path) -> int:
    """Pre-flight: model load + persona draw + purchase call + file checks.

    Model-call budget (<= 4): one manager model load, up to two persona
    draws (a second only when the first does not parse), one persona
    purchase call; the write-through checks make no model call. The model
    loaded before the smoke is restored afterwards.
    """
    run_dir = out / (
        settings.run_name or f"smoke-{datetime.now().strftime('%Y%m%dT%H%M%S')}"
    )
    run_dir.mkdir(parents=True, exist_ok=True)
    wall_started = time.monotonic()
    started = _now()

    def log(text: str) -> None:
        print(f"[{time.strftime('%H:%M:%S')}] {text}", flush=True)

    try:
        prior = _manager_status(settings.manager_url).get(str(settings.port), {})
    except OSError as exc:
        log(f"error: cannot reach model manager {settings.manager_url}: {exc}")
        return 2
    prior_model = prior.get("model")
    calls: list[dict[str, Any]] = []
    pool_file = run_dir / "smoke_persona.jsonl"
    try:
        log(
            f"smoke: loading {settings.model} on :{settings.port} "
            f"(previous: {prior_model or 'none'})"
        )
        _load_model(settings.manager_url, settings.model, settings.port)
        calls.append({"call": "model_load", "ok": True})
        products = json.loads(products_path.read_text(encoding="utf-8"))
        if isinstance(products, dict):
            products = products.get("products") or []
        item = products[0]
        persona = _draw_smoke_persona(settings, item, pool_file, calls, log)
        design = _SWEEP._build_design(
            [100.0], ["blinded"], settings.seed, [], "demographics"
        )
        records = _run_smoke_purchase(settings, item, persona, design, calls)
        if records:
            _SWEEP._write_records(run_dir / f"smoke_{settings.port}", records)
        _write_smoke_manifest(
            settings, run_dir, design, products, started, calls, persona, pool_file
        )
    finally:
        if prior_model and prior_model != settings.model:
            try:
                log(f"restoring {prior_model} on :{settings.port} (as-found state)...")
                _load_model(settings.manager_url, prior_model, settings.port)
            except RuntimeError as exc:
                log(f"warning: could not restore {prior_model}: {exc}")
    return _report_smoke(settings, run_dir, calls, pool_file, wall_started, log)


def _smoke_direct_chat(settings: Settings, messages: list[dict[str, str]]) -> str:
    """One raw chat POST with no max_tokens (like the persona pool draws)."""
    payload = {"model": settings.model, "messages": messages, "temperature": 1.0}
    url = f"{settings.base_url.rstrip('/')}/v1/chat/completions"
    try:
        status, body = _post_json(url, payload, 120.0)
    except OSError:
        return ""
    if status != 200:
        return ""
    try:
        content = json.loads(body)["choices"][0]["message"].get("content")
        return content if isinstance(content, str) else ""
    except (json.JSONDecodeError, KeyError, IndexError):
        return ""


def _draw_smoke_persona(
    settings: Settings,
    item: dict[str, Any],
    pool_file: Path,
    calls: list[dict[str, Any]],
    log: Callable[[str], None],
) -> dict[str, Any] | None:
    """Draw up to two personas for the smoke (second only if first fails).

    Every raw answer is saved next to the pool file
    (smoke_persona_raw_N.txt) so a failed pre-flight leaves direct evidence
    of what the model wrote.
    """
    from fos.experiments import personas  # noqa: PLC0415

    for attempt in range(2):
        messages = [
            {"role": "system", "content": personas.PERSONA_SYSTEM},
            {
                "role": "user",
                "content": personas.build_persona_elicitation_prompt(
                    item["category"], item["product"]
                ),
            },
        ]
        raw = _smoke_direct_chat(settings, messages)
        raw_file = pool_file.with_name(f"smoke_persona_raw_{attempt + 1}.txt")
        raw_file.write_text(raw or "", encoding="utf-8")
        persona = personas.parse_persona(raw)
        calls.append(
            {
                "call": "persona_draw",
                "attempt": attempt + 1,
                "ok": persona is not None,
                "chars": len(raw or ""),
                "raw_file": str(raw_file),
            }
        )
        if persona is not None:
            with pool_file.open("w", encoding="utf-8") as out_handle:
                out_handle.write(json.dumps(persona) + "\n")
            return persona
        log(
            f"smoke: persona draw {attempt + 1} did not parse "
            f"({len(raw or '')} chars; saved to {raw_file.name})"
        )
    return None


def _run_smoke_purchase(
    settings: Settings,
    item: dict[str, Any],
    persona: dict[str, Any] | None,
    design: Any,
    calls: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """One purchase call (with the drawn persona, else the plain survey)."""
    chat = _SWEEP.build_sweep_chat_fn(settings.base_url, settings.model, 16, 120.0)
    if persona is not None:
        personas_by_product = {
            item["product"]: {
                "category": item["category"],
                "regular_price": item["regular_price"],
                "personas": [persona],
            }
        }
        records, _skipped = run_persona_sweep(
            design,
            personas_by_product,
            settings.model,
            chat,
            blinding="blinded",
            persona_depth="demographics",
            seed=settings.seed,
        )
    else:
        records = run_sweep(
            design,
            [item],
            settings.model,
            chat,
            draws=1,
            blinding="blinded",
            seed=settings.seed,
            persona_depth="none",
        )
    parsed = sum(1 for record in records if record.get("succeeded"))
    calls.append(
        {
            "call": "purchase",
            "records": len(records),
            "parsed": parsed,
            "parse_rate": parsed / max(1, len(records)),
        }
    )
    return records


def _write_smoke_manifest(
    settings: Settings,
    run_dir: Path,
    design: Any,
    products: list[dict[str, Any]],
    started: str,
    calls: list[dict[str, Any]],
    persona: dict[str, Any] | None,
    pool_file: Path,
) -> None:
    """Write the smoke run's small manifest.json."""
    write_manifest(
        run_dir / "manifest.json",
        design,
        settings.model,
        1,
        "blinded",
        products[:1],
        settings.base_url,
        extra={
            "smoke": True,
            "calls": calls,
            "started": started,
            "finished": _now(),
            "commit_sha": _repo_sha(),
            "persona_parsed": persona is not None,
            "pool_file": str(pool_file) if persona is not None else None,
        },
    )


def _report_smoke(
    settings: Settings,
    run_dir: Path,
    calls: list[dict[str, Any]],
    pool_file: Path,
    wall_started: float,
    log: Callable[[str], None],
) -> int:
    """Check the smoke outputs, print them, and return the exit code."""
    jsonl = run_dir / f"smoke_{settings.port}.jsonl"
    csv = run_dir / f"smoke_{settings.port}.csv"
    wall_s = time.monotonic() - wall_started
    checks = {
        "manager_load_ok": any(
            c.get("call") == "model_load" and c.get("ok") for c in calls
        ),
        "pool_file_written": pool_file.exists() and pool_file.stat().st_size > 0,
        "records_written": jsonl.exists()
        and csv.exists()
        and jsonl.stat().st_size > 0
        and csv.stat().st_size > 0,
        "manifest_written": (run_dir / "manifest.json").exists(),
    }
    purchase = next((c for c in calls if c.get("call") == "purchase"), {})
    log("smoke results:")
    for name, ok in checks.items():
        log(f"  {name}: {'OK' if ok else 'FAIL'}")
    log(
        f"  purchase parse: {purchase.get('parse_rate', 0.0):.3f} "
        f"({purchase.get('parsed', 0)}/{purchase.get('records', 0)} records)"
    )
    log(f"  model calls made: {len(calls)} (see manifest.json)")
    log(f"  output: {run_dir}")
    log(f"  smoke wall time: {wall_s:.1f} s")
    manifest_path = run_dir / "manifest.json"
    if manifest_path.exists():
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        payload["smoke_checks"] = checks
        payload["smoke_wall_seconds"] = wall_s
        manifest_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return 0 if all(checks.values()) else 1
