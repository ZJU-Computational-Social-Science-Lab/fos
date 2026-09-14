"""The R1-YESNO-QWENEXT queue specification: three more Qwen models on
qwen3.8-27b's slice, planned and printed offline.

R1-YESNO-QWENEXT re-runs the R1-YESNO first-token yes/no logprob
experiment with three additional Qwen models. Every one of the three
answers the SAME persona slice that qwen/qwen3.8-27b (queue index 2 in
launch_queue.MODEL_QUEUE) answered in R1-YESNO - pool personas [40, 60)
of every product's 100-persona pool - so the new models are directly
comparable to qwen3.8-27b (a shared slice, NOT a partition of the pool).
The geometry is the R1-YESNO geometry exactly: one scoring pass per
prompt, so per model 2 x 40 x 11 x 1 = 880 bare + 2 x 40 x 20 x 11 =
17,600 demographics = 18,480 calls, and the three models together
55,440 across 12 legs. None of the three models has a top-k or
control-sequence override (qwen3.8-27b needed none; the record flags
surface any surprise at analysis time), and the pools are reused from
the same archived run as every other profile. Like launch_queue.py this
module is a pure specification: it opens no sockets and writes no files;
the network only runs inside the runner's run paths.

What each function does (plain language):
    qwenext_persona_slice(index)  - The shared [40, 60) slice every
                                    QWENEXT model answers (the exact
                                    slice qwen3.8-27b answered in
                                    R1-YESNO); refuses an index outside
                                    the 3-model queue instead of
                                    silently slicing empty.
    _qwenext_model_meta(...)      - The plan's summary of one model: its
                                    calls and its shared persona slice.
    build_qwenext_plan(...)       - The queue plan: 12 legs, per-model
                                    and total call counts (18,480 x 3).
    print_qwenext_dry_run(...)    - The printed plan (dry run) - no
                                    manager, no server, no grammar.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPT_DIR = _REPO_ROOT / "scripts"
_SRC = _REPO_ROOT / "src"
for _dir in (_SCRIPT_DIR, _SRC):
    if str(_dir) not in sys.path:
        sys.path.insert(0, str(_dir))

from launch_queue import (  # noqa: E402
    DEFAULT_POOLS_FROM,
    LOGP_NONE_DRAWS,
    MODEL_QUEUE,
    PERSONAS_PER_MODEL,
    POOL_PERSONAS_PER_PRODUCT,
    _resolve_pools_from,
    persona_slice,
)
from launch_support import BASE_DEPTHS, BLINDINGS, _safe_model_name  # noqa: E402

# The queue's run-level profile name (the YESNO_PROFILE naming pattern).
QWENEXT_PROFILE = "R1-YESNO-QWENEXT"
# Manager registry ids (~/fos-model-manager MODEL_REGISTRY), in the run
# order the queue loads and runs them back to back, then unloads each.
QWENEXT_MODEL_QUEUE = (
    "qwen/qwen3.6-35b-a3b",
    "qwen3.6-35b-a3b-uncensored-hauhaucs-aggressive",
    "qwen3-4b",
)
# The R1-YESNO model whose persona slice every QWENEXT model shares:
# qwen/qwen3.8-27b answered pool personas [40, 60) in R1-YESNO, so all
# three new models answer exactly those personas of every product.
QWENEXT_SLICE_MODEL = "qwen/qwen3.8-27b"
_SLICE_INDEX = MODEL_QUEUE.index(QWENEXT_SLICE_MODEL)


def qwenext_persona_slice(model_index: int) -> tuple[int, int]:
    """The pool index range every QWENEXT model answers: [40, 60).

    All three models share qwen3.8-27b's R1-YESNO slice by design (a
    shared slice, not a partition), so their answers stay directly
    comparable. An index outside the 3-model queue raises instead of
    silently slicing empty - the same never-guess convention as
    launch_queue.persona_slice.
    """
    if not 0 <= model_index < len(QWENEXT_MODEL_QUEUE):
        raise ValueError(
            f"model_index {model_index} is outside the QWENEXT queue "
            f"(0..{len(QWENEXT_MODEL_QUEUE) - 1})"
        )
    return persona_slice(_SLICE_INDEX)


def _qwenext_model_meta(
    model_index: int, product_count: int, level_count: int
) -> dict[str, Any]:
    """The plan's summary of one model: its calls and persona slice."""
    model = QWENEXT_MODEL_QUEUE[model_index]
    start, stop = qwenext_persona_slice(model_index)
    none_calls = 2 * product_count * level_count * LOGP_NONE_DRAWS
    demographics_calls = 2 * product_count * PERSONAS_PER_MODEL * level_count
    return {
        "model": model,
        "model_index": model_index,
        "safe_model": _safe_model_name(model),
        "persona_slice": [start, stop],
        "personas_per_product": PERSONAS_PER_MODEL,
        "none_calls": none_calls,
        "demographics_calls": demographics_calls,
        "total_calls": none_calls + demographics_calls,
    }


def build_qwenext_plan(
    product_count: int,
    level_count: int,
    *,
    levels: list[float] | None = None,
    seed: int = 42,
    pool_seed: int = 42,
    profile: str = QWENEXT_PROFILE,
) -> dict[str, Any]:
    """The whole QWENEXT plan: 12 legs, per-model and total call counts.

    legs holds the 12 (model x depth x blinding) targets in queue order:
    for each model, none_blinded, none_unblinded, demographics_blinded,
    demographics_unblinded. None legs carry 40 x levels x 1 calls each,
    demographics legs 40 x 20 x levels each; per model that is the
    R1-YESNO 880 + 17,600 = 18,480 one-pass scoring calls, and the three
    models together 55,440. Every model answers the SAME shared [40, 60)
    slice, the pools are reused by default (pool_draws 0), and none of
    the three models holds a top-k or control-sequence override (the
    launch_queue maps stay authoritative; qwen3.8-27b needed none).
    """
    levels = list(levels) if levels is not None else []
    targets: list[dict[str, Any]] = []
    models: list[dict[str, Any]] = []
    for index in range(len(QWENEXT_MODEL_QUEUE)):
        meta = _qwenext_model_meta(index, product_count, level_count)
        models.append(meta)
        for depth in BASE_DEPTHS:
            for blinding in BLINDINGS:
                calls = (
                    product_count * level_count * LOGP_NONE_DRAWS
                    if depth == "none"
                    else product_count * PERSONAS_PER_MODEL * level_count
                )
                targets.append(
                    {
                        "model": meta["model"],
                        "model_index": index,
                        "safe_model": meta["safe_model"],
                        "depth": depth,
                        "blinding": blinding,
                        "calls": calls,
                    }
                )
    return {
        "profile": profile,
        "models": models,
        "legs": targets,
        "sweep_calls": sum(int(leg["calls"]) for leg in targets),
        "levels": levels,
        "k": POOL_PERSONAS_PER_PRODUCT,
        "draws": LOGP_NONE_DRAWS,
        "per_model_personas": PERSONAS_PER_MODEL,
        "seed": seed,
        "pool_seed": pool_seed,
        "pool_draws": 0,  # pools are reused (no persona draws) by default
    }


def print_qwenext_dry_run(
    args: Any,
    products: list[dict[str, Any]],
    plan: dict[str, Any],
    run_dir: Path,
) -> None:
    """Print the whole QWENEXT plan and exit (dry run, fully offline).

    Mirrors the other queues' plan printer: profile header, the three
    models with their SHARED persona slice, per-leg and total call
    counts, the pool source and the output layout. The purchase grammar
    never appears - this profile is grammar-free yes/no first-token
    logprob scoring, like R1-YESNO.
    """
    profile = plan.get("profile", QWENEXT_PROFILE)
    per_model = int(plan["sweep_calls"] / len(plan["models"]))
    source = _resolve_pools_from(getattr(args, "pools_from", ""))
    print(f"{profile} launch plan (dry run)")
    print(
        f"  queue         {len(plan['models'])} models, one invocation "
        f"(manager {args.manager_url})"
    )
    for meta in plan["models"]:
        start, stop = meta["persona_slice"]
        print(
            f"    [{meta['model_index']}] {meta['model']:<36} "
            f"pool personas {start}-{stop - 1} (shared qwen3.8-27b slice), "
            f"{plan['draws']} scoring pass/cell"
        )
    print("  grammar       none (grammar-free yes/no first-token logprobs)")
    print(
        f"  products      {len(products)} from "
        f"{Path(args.products).name if Path(args.products).exists() else args.products}"
    )
    print(
        f"  levels        {len(plan['levels'])} price levels; "
        "depths none, demographics x blinded, unblinded"
    )
    print(f"  persona pool  {plan['k']} personas/product, seed {plan['pool_seed']}")
    if source is not None:
        print(f"    reused from {source}  (pools from --pools-from)")
    else:
        given = getattr(args, "pools_from", "")
        label = "default" if given == DEFAULT_POOLS_FROM else "--pools-from"
        print(
            f"    {label} pool source {given or '(none)'} not found in this "
            "checkout; the run will regenerate a deterministic pool-seed-42 "
            f"pool ({plan['k']} personas/product) as today"
        )
    print(f"  legs ({len(plan['legs'])}, per model)")
    for meta in plan["models"]:
        print(
            f"    {meta['model']:<36} "
            f"none {meta['none_calls']:,} calls (2 x "
            f"{int(meta['none_calls'] / 2):,}) + demographics "
            f"{meta['demographics_calls']:,} calls (2 x "
            f"{int(meta['demographics_calls'] / 2):,})"
        )
    print(
        f"  queue calls   {plan['sweep_calls']:,} total "
        f"({len(plan['models'])} models x {per_model:,})"
    )
    print(
        f"  prompts       {per_model:,} scoring prompts per model "
        f"({plan['sweep_calls']:,} total, first_token yes/no logprobs)"
    )
    print(
        f"  outputs       {run_dir}/  (per-model leg dirs, results.csv "
        "appended continuously, progress.json, manifest.json)"
    )
