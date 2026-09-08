#!/usr/bin/env python3
"""Launch the Gui & Toubia replication sweep with one command (pre-flight).

The entry point of the study's launch wrapper. It parses the flags, counts
every call the run will make (persona-pool draws + the sweep legs), prints
the plan in --dry-run, runs the <=4-call pre-flight in --smoke, and in a
real run loads the model through the manager, builds the persona pools,
then runs the (depth x blinding) sweep legs concurrently. All the machinery
it drives lives in two sibling modules: launch_support.py (model manager +
persona pools) and launch_sweep.py (sweep legs, watchdog, manifest, smoke).
Both wrap the study's existing tools (scripts/generate_personas.py and
scripts/unblinding_sweep.py) without changing what either tool does.

Profiles (from the measured pilot numbers in RESULT-1501):
    R1   (default) - K=100 personas/product, depths none+demographics,
                     40 products, 11 price levels, draws 50.
    FULL           - K=500 (the paper's n). Prints the measured full-grid
                     figure (pilot ~41-45 h for the 880k-call grid) and
                     only fires with --i-know-this-is-41h.
`--stages` names the Appendix E tiers stage2..stage12; those stages are not
wired into the product-sweep pipeline yet and refuse cleanly (their pools
come from the Twin-2K-500 panel, their renderer is not plumbed into the
sweep kit). They are reserved for later stage-sensitivity runs.

Function map: main (dispatch) -> _run (real launch) with helpers
_pending_legs and _launch_legs; plan/ETA helpers _plan, _legs_from_depths,
_eta_estimates, _build_run_name, _print_dry_run, _print_eta_block;
flag handling _parse_args, _usage_error, _settings_from; utilities
_start_thread and _make_log.
"""

from __future__ import annotations

import argparse
import math
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))
if str(_REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "src"))

from launch_support import (  # noqa: E402
    BASE_DEPTHS,
    BLINDINGS,
    DEFAULT_LEVELS,
    DEFAULT_MANAGER,
    DEFAULT_MODEL,
    PILOT_BATCH_SPEEDUP,
    PILOT_POOL_DRAW_SECONDS,
    PILOT_PERSONA_SWEEP_SECONDS,
    PILOT_SWEEP_SECONDS,
    PROFILES,
    STAGE_DEPTHS,
    Settings,
    _ensure_model,
    _load_pool_personas,
    _load_products,
    _pool_phase,
    _repo_sha,
    _resolve_products,
    _safe_model_name,
)
from launch_sweep import (  # noqa: E402
    _leg_is_done,
    _make_chat,
    _progress_line,
    _run_one_leg,
    _smoke,
    _watchdog,
    _write_run_manifest,
)

DEFAULT_PRODUCTS = "data/configs/unblinding_products.json"
DEFAULT_OUT = "results/unblinding"
DEFAULT_OVERDRAW = 1.2
PROGRESS_EVERY = 1000


def _make_log() -> Callable[[str], None]:
    """A timestamped console logger that flushes every line."""

    def _write(text: str) -> None:
        print(f"[{time.strftime('%H:%M:%S')}] {text}", flush=True)

    return _write


log = _make_log()


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    """Read the command-line flags into one settings object."""
    parser = argparse.ArgumentParser(
        prog="launch_grid",
        description=(
            "Launch the Gui & Toubia replication sweep (persona pools + "
            "price sweep) with one command; smoke and dry-run modes for "
            "pre-flight."
        ),
    )
    parser.add_argument("--profile", choices=sorted(PROFILES), default="R1")
    parser.add_argument(
        "--k",
        type=int,
        default=None,
        help="personas per product (default R1=100, FULL=500)",
    )
    parser.add_argument(
        "--draws", type=int, default=50, help="plain-sweep draws per product and level"
    )
    parser.add_argument("--levels", default=DEFAULT_LEVELS)
    parser.add_argument("--products", default=DEFAULT_PRODUCTS)
    parser.add_argument("--pool-seed", type=int, default=42)
    parser.add_argument("--pool-overdraw", type=float, default=DEFAULT_OVERDRAW)
    parser.add_argument(
        "--stages",
        default="",
        help="comma list of Appendix "
        "E stage depths (stage2..stage12); reserved for "
        "later stage-sensitivity runs",
    )
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--port", type=int, default=8080, choices=(8080, 8082))
    parser.add_argument("--manager-url", default=DEFAULT_MANAGER)
    parser.add_argument(
        "--base-url",
        default="",
        help="chat server base url (default http://127.0.0.1:<port>)",
    )
    parser.add_argument("--out", default=DEFAULT_OUT)
    parser.add_argument("--run-name", default="")
    parser.add_argument("--seed", type=int, default=42, help="sweep design seed")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--i-know-this-is-41h", action="store_true")
    parser.add_argument("--progress-every", type=int, default=PROGRESS_EVERY)
    return parser.parse_args(argv)


def _usage_error(message: str) -> None:
    """Print a usage error to stderr and exit with code 2."""
    print(message, file=sys.stderr)
    raise SystemExit(2)


def _depths_for(stages_spec: str) -> list[str]:
    """The depth ladder to run; stage tiers refuse with the reason."""
    stages = [piece.strip() for piece in stages_spec.split(",") if piece.strip()]
    for stage in stages:
        if stage not in STAGE_DEPTHS:
            _usage_error(
                f"error: unknown stage depth {stage!r} (choose "
                f"from {', '.join(STAGE_DEPTHS)})"
            )
    if stages:
        _usage_error(
            "error: stage depths are not runnable yet: their pools come from "
            "the Appendix E Twin-2K-500 panel and their renderer is not "
            "plumbed into unblinding_sweep. Tonight's launch is depths "
            "none+demographics; --stages is reserved for the later "
            "stage-sensitivity pipeline."
        )
    return list(BASE_DEPTHS)


def _legs_from_depths(
    depths: list[str],
    product_count: int,
    level_count: int,
    k: int,
    draws: int,
) -> list[dict[str, Any]]:
    """The (depth x blinding) legs of the run with their call counts."""
    legs: list[dict[str, Any]] = []
    for depth in depths:
        per_blinding = (
            product_count * level_count * draws
            if depth == "none"
            else product_count * k * level_count
        )
        for blinding in BLINDINGS:
            legs.append({"depth": depth, "blinding": blinding, "calls": per_blinding})
    return legs


def _eta_estimates(plain_calls: int, persona_calls: int) -> tuple[float, float]:
    """Batched sweep hours (low/high) from the measured pilot latencies."""
    low = (
        (plain_calls + persona_calls)
        * PILOT_SWEEP_SECONDS
        / PILOT_BATCH_SPEEDUP
        / 3600.0
    )
    high = (
        (
            plain_calls * PILOT_SWEEP_SECONDS
            + persona_calls * PILOT_PERSONA_SWEEP_SECONDS
        )
        / PILOT_BATCH_SPEEDUP
        / 3600.0
    )
    return low, high


def _plan(args: argparse.Namespace, products: list[dict[str, Any]]) -> dict[str, Any]:
    """Count every call the run will make and estimate its wall time.

    Plain (none) legs draw once per product x level x draw; persona legs
    draw once per product x persona x level at temperature 0. Pool draws
    are the persona requests generate_personas makes (overdrawn). ETA uses
    the measured pilot latencies and pool-draw estimate (see
    _eta_estimates).
    """
    k = PROFILES[args.profile] if args.k is None else args.k
    levels = [float(p) for p in args.levels.split(",") if p.strip()]
    if not levels:
        _usage_error("error: no price levels parsed from --levels")
    depths = _depths_for(args.stages)
    legs = _legs_from_depths(depths, len(products), len(levels), k, args.draws)
    sweep_calls = sum(leg["calls"] for leg in legs)
    plain = sum(leg["calls"] for leg in legs if leg["depth"] == "none")
    pool_draws = (
        len(products) * math.ceil(k * args.pool_overdraw)
        if any(depth != "none" for depth in depths)
        else 0
    )
    return {
        "profile": args.profile,
        "k": k,
        "levels": levels,
        "depths": depths,
        "legs": legs,
        "sweep_calls": sweep_calls,
        "pool_draws": pool_draws,
        "sweep_hours": _eta_estimates(plain, sweep_calls - plain),
        "pools_hours": pool_draws * PILOT_POOL_DRAW_SECONDS / 3600.0,
        "sequential_hours": sweep_calls * PILOT_SWEEP_SECONDS / 3600.0,
    }


def _build_run_name(args: argparse.Namespace) -> str:
    """Default run name: profile, model stem and local time."""
    if args.run_name:
        return args.run_name
    stem = _safe_model_name(args.model).replace("nvidia_", "")
    stamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    return f"{args.profile}-{stem}-{stamp}"


def _print_eta_block(plan: dict[str, Any], leg_count: int) -> None:
    """Print the ETA section of the dry run."""
    print("  ETA from measured pilot latencies (RESULT-1501)")
    print(
        f"    pools       ~{plan['pools_hours']:.1f} h sequential "
        f"(~{PILOT_POOL_DRAW_SECONDS:g} s/draw)"
    )
    print(
        f"    sweep       ~{plan['sweep_hours'][0]:.1f} - "
        f"{plan['sweep_hours'][1]:.1f} h with {leg_count} legs concurrent "
        f"(measured ~{PILOT_BATCH_SPEEDUP:g}x on 4 slots)"
    )
    print(
        f"    total       ~{plan['pools_hours'] + plan['sweep_hours'][0]:.1f} - "
        f"{plan['pools_hours'] + plan['sweep_hours'][1]:.1f} h "
        f"(sequential single slot: ~{plan['sequential_hours']:.1f} h)"
    )


def _print_dry_run(
    args: argparse.Namespace,
    products: list[dict[str, Any]],
    plan: dict[str, Any],
) -> None:
    """Show the full plan and its ETA, then exit."""
    base = args.base_url or f"http://127.0.0.1:{args.port}"
    run_name = _build_run_name(args)
    print(f"{args.profile} launch plan (dry run)")
    print(f"  model        {args.model} on {base} (manager {args.manager_url})")
    print(f"  products     {len(products)} from {_resolve_products(args.products)}")
    print(f"  depths       {', '.join(plan['depths'])} x {', '.join(BLINDINGS)}")
    print(
        f"  K            {plan['k']} personas/product (pool-seed "
        f"{args.pool_seed}, overdraw {args.pool_overdraw})"
    )
    print("  legs")
    for leg in plan["legs"]:
        kind = "plain" if leg["depth"] == "none" else f"personas K={plan['k']}"
        print(
            f"    {leg['depth']}_{leg['blinding']:<16} {kind:<16} "
            f"{leg['calls']:,} calls"
        )
    print(
        f"  sweep calls  {plan['sweep_calls']:,} total; pool draws ~"
        f"{plan['pool_draws']:,}"
    )
    _print_eta_block(plan, len(plan["legs"]))
    print(
        f"  outputs      {Path(args.out) / run_name}/  (manifest.json, "
        f"pools/, one directory per leg)"
    )
    if args.profile == "FULL":
        print(
            "  FULL note   K=500 is the paper's n; the pilot's measured "
            "full-grid figure is"
        )
        print(
            "              ~41-45 h for the 880,000-call grid at 4-slot "
            "batching. Running FULL"
        )
        print("              requires --i-know-this-is-41h.")


def _settings_from(args: argparse.Namespace, run_name: str) -> Settings:
    """Map parsed flags onto the support module's settings object."""
    return Settings(
        model=args.model,
        port=args.port,
        manager_url=args.manager_url,
        base_url=args.base_url or f"http://127.0.0.1:{args.port}",
        out=Path(args.out),
        run_name=run_name,
        pool_seed=args.pool_seed,
        pool_overdraw=args.pool_overdraw,
        seed=args.seed,
        draws=args.draws,
        progress_every=args.progress_every,
        products_path=args.products,
    )


def _start_thread(target: Any, args: tuple) -> threading.Thread:
    """Start one daemon thread running target(*args) and return it."""
    thread = threading.Thread(target=target, args=args, daemon=True)
    thread.start()
    return thread


def main(argv: list[str] | None = None) -> int:
    """Entry point: parse flags, then smoke, dry-run, or the full run."""
    args = _parse_args(argv)
    products_path = _resolve_products(args.products)
    if args.smoke:
        return _smoke(
            _settings_from(args, args.run_name), products_path, Path(args.out)
        )
    if args.profile == "FULL" and not args.i_know_this_is_41h and not args.dry_run:
        print(
            "error: profile FULL is the paper-scale run (measured ~41-45 h "
            "for the 880k-call grid at 4-slot batching); pass "
            "--i-know-this-is-41h to fire it",
            file=sys.stderr,
        )
        return 2
    products = _load_products(products_path)
    if not products:
        print("error: the products file lists no products", file=sys.stderr)
        return 2
    plan = _plan(args, products)
    if args.dry_run:
        _print_dry_run(args, products, plan)
        return 0
    return _run(
        args, plan, products, products_path, _settings_from(args, _build_run_name(args))
    )


def _run(
    args: argparse.Namespace,
    plan: dict[str, Any],
    products: list[dict[str, Any]],
    products_path: Path,
    settings: Settings,
) -> int:
    """Run the real launch: model load, pools, concurrent legs, manifest."""
    run_dir = settings.out / settings.run_name
    if run_dir.exists() and (run_dir / "manifest.json").exists() and not args.resume:
        print(
            f"error: run dir {run_dir} already has a manifest.json; pass "
            f"--resume to continue it or choose a new --run-name",
            file=sys.stderr,
        )
        return 2
    run_dir.mkdir(parents=True, exist_ok=True)
    started_wall = time.monotonic()
    started = datetime.now().astimezone().isoformat()
    log(f"run {settings.run_name} starting (commit {_repo_sha() or 'unknown'})")
    k = plan["k"]
    safe_model = _safe_model_name(settings.model)
    targets = [
        {"depth": leg["depth"], "blinding": leg["blinding"]} for leg in plan["legs"]
    ]
    pending = _pending_legs(args, run_dir, safe_model, targets)
    if len(pending) < len(targets):
        log(
            f"resume: {len(targets) - len(pending)}/{len(targets)} legs "
            f"already complete - skipping"
        )
    if not pending:
        log("nothing to run (all legs complete)")
        _write_run_manifest(
            settings,
            plan,
            products_path,
            run_dir,
            started,
            datetime.now().astimezone().isoformat(),
            [],
            None,
        )
        return 0
    _ensure_model(settings, log)
    pool_summary = None
    personas_by_product = None
    if any(leg["depth"] != "none" for leg in pending):
        pool_summary = _pool_phase(settings, products, products_path, run_dir, k, log)
        personas_by_product = _load_pool_personas(run_dir, products, k)
        if not personas_by_product:
            print(
                f"error: no pool files matched any product under {run_dir / 'pools'!r}",
                file=sys.stderr,
            )
            return 2
    results = _launch_legs(
        settings, plan, products, personas_by_product, run_dir, safe_model, pending
    )
    _write_run_manifest(
        settings,
        plan,
        products_path,
        run_dir,
        started,
        datetime.now().astimezone().isoformat(),
        results,
        pool_summary,
    )
    return _report_run(results, settings, run_dir, started_wall)


def _pending_legs(
    args: argparse.Namespace,
    run_dir: Path,
    safe_model: str,
    targets: list[dict[str, str]],
) -> list[dict[str, str]]:
    """The legs still to run: all of them, or only the unfinished on resume."""
    if not args.resume:
        return targets
    return [leg for leg in targets if not _leg_is_done(run_dir, safe_model, leg)]


def _launch_legs(
    settings: Settings,
    plan: dict[str, Any],
    products: list[dict[str, Any]],
    personas_by_product: dict[str, Any] | None,
    run_dir: Path,
    safe_model: str,
    pending: list[dict[str, str]],
) -> list[dict[str, Any]]:
    """Start the pending legs concurrently and wait for every one of them."""
    pending_calls = sum(
        leg["calls"]
        for leg in plan["legs"]
        if not _leg_is_done(run_dir, safe_model, leg)
    )
    chat_fn, state, abort = _make_chat(
        settings,
        pending_calls,
        lambda d, t, p, r: log(_progress_line(d, t, p, r)),
    )
    done_event = threading.Event()
    _start_thread(_watchdog, (settings, abort, done_event, log))
    results: list[dict[str, Any]] = []
    log(
        f"launching {len(pending)} legs concurrently on {settings.base_url} "
        f"({pending_calls:,} calls planned)"
    )
    threads = [
        _start_thread(
            _run_one_leg,
            (
                settings,
                plan,
                products,
                personas_by_product,
                run_dir,
                chat_fn,
                leg,
                results,
                log,
            ),
        )
        for leg in pending
    ]
    for thread in threads:
        thread.join()
    done_event.set()
    log(
        f"finished: {state['done']:,} calls, "
        f"parse {100.0 * state['parsed'] / max(1, state['done']):.1f}%"
    )
    return results


def _report_run(
    results: list[dict[str, Any]],
    settings: Settings,
    run_dir: Path,
    started_wall: float,
) -> int:
    """Print failures or the completion line and return the exit code."""
    failed = [r for r in results if not r.get("ok")]
    if failed:
        for result in failed:
            print(
                f"leg {result['depth']}_{result['blinding']} failed: "
                f"{result.get('error')}",
                file=sys.stderr,
            )
        print(
            f"run {settings.run_name} finished with {len(failed)} failed "
            f"leg(s); rerun with --resume --run-name {settings.run_name} "
            f"to retry them",
            file=sys.stderr,
        )
        return 1
    log(
        f"run {settings.run_name} complete in "
        f"{(time.monotonic() - started_wall) / 3600.0:.2f} h"
    )
    log(f"results: {run_dir}/manifest.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
