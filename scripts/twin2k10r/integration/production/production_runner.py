# This file is the production runner's single command: one launch builds
# the run folder, draws the real-respondent persona pool (Config A) once,
# writes the run manifest, and walks the merged 31-experiment grid — 15
# models sequentially (clean models first, the two flagged models last),
# one model loaded at any moment, llama-server on port 8080. Twin-style
# experiments run through the twin driver, T2KX experiments through the
# frozen expansion pipeline with the adapted pool. Every finished record
# is on disk before the next call starts, so a killed run resumes with
# --run-dir and skips what is already durable. Modes:
#   (default)   — the production grid into /home/justin/work/extended_run-<stamp>/
#   --smoke     — 2 personas, one model, both pipelines x both arms x both
#                 scoring types, into a SMOKE run folder (never production)
#   --dry-run   — print the cell counts, call nothing, write nothing
#   --run-dir   — resume an existing folder
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[4]
for _dir in (str(_REPO_ROOT), str(_REPO_ROOT / "scripts")):
    if _dir not in sys.path:
        sys.path.insert(0, _dir)

from twin2k10r.integration.production import (  # noqa: E402
    driver_expansion,
    driver_twin,
    model_ids,
    run_plan,
    safeguards,
)

SMOKE_MODEL = "qwen3-4b"
SMOKE_PERSONAS = 2
# Run folders live under the WRITABLE root given by EXTENDED_RUN_ROOT
# (default: this repository worktree). The originally planned
# /home/justin/work/ is a read-only mount on this machine, so the
# environment variable decides where production output lands.
RUN_ROOT = Path(os.environ.get(
    "EXTENDED_RUN_ROOT", str(Path(__file__).resolve().parents[4])))
RUN_PREFIX = "extended_run-"
SMOKE_PREFIX = "extended_run-SMOKE-"


def log(message: str) -> None:
    """One timestamped progress line on stdout (and the run's log file)."""
    print(f"[{datetime.now(timezone.utc).isoformat()}] {message}", flush=True)


def parse_args(argv=None):
    """The runner's command-line interface (see the module docstring)."""
    parser = argparse.ArgumentParser(
        prog="python -m twin2k10r.integration.production.production_runner",
        description="Extended production run: merged 31-experiment grid, "
                    "15 models, Config A real-respondent pool, port 8080.")
    parser.add_argument("--run-dir", type=Path, default=None,
                        help="existing run folder to resume")
    parser.add_argument("--models", default=None,
                        help="comma-separated subset of study model ids")
    parser.add_argument("--smoke", action="store_true",
                        help="tiny end-to-end rehearsal into a SMOKE folder")
    parser.add_argument("--dry-run", action="store_true",
                        help="print cell counts; call nothing")
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    parser.add_argument("--max-personas", type=int, default=None,
                        help="cap personas (production default: all 100)")
    return parser.parse_args(argv)


def new_run_dir(smoke: bool) -> Path:
    """A fresh run folder; smoke runs can never mix with production."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    return RUN_ROOT / f"{SMOKE_PREFIX if smoke else RUN_PREFIX}{stamp}"


def resolve_models(requested):
    """The validated model list (a typo stops the run before any work)."""
    models = run_plan.ordered_models()
    if requested is None:
        return models
    chosen = [name.strip() for name in requested.split(",") if name.strip()]
    for model in chosen:
        model_ids.server_model_id(model)  # raises on a typo
    return [model for model in models if model in chosen]


def sha256_of(path: Path) -> str:
    """The hex sha256 of a file (provenance in the manifest)."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def dataset_hashes(run_dir: Path) -> dict:
    """The provenance hashes stamped on every record and the manifest.

    dataset_sha256 is the pool's dataset manifest hash when present (the
    fingerprint of the exact Twin-2K-500 mirror the pool was drawn from);
    otherwise the shipped stimuli file's hash stands in.
    """
    manifest = Path(run_dir) / "pools" / "dataset_manifest.json"
    stimuli = _REPO_ROOT / "data" / "configs" / "twin2k10_stimuli.json"
    restored = (_REPO_ROOT / "scripts" / "twin2k10r" / "stimuli_restored"
                / "data" / "restored_stimuli.json")
    return {
        "dataset_sha256": (sha256_of(manifest) if manifest.exists()
                           else sha256_of(stimuli)),
        "stimuli_sha256": sha256_of(stimuli),
        "restored_stimuli_sha256": sha256_of(restored),
    }


def build_pools(run_dir: Path, log) -> tuple[list[dict], list[dict]]:
    """The Config A pool for twin legs + its adapted copy for expansion.

    The CANONICAL hash-pinned Stage 0 pool is reused verbatim (the same
    100 respondents everywhere; personas are never regenerated mid-run).
    Only when the canonical pool is unavailable does the pool get built
    from the dataset mirror (deterministic, same seed). The expansion
    adapter renames the three dataset fields and drops bookkeeping keys
    without touching any value.
    """
    import shutil

    from twin2k10r.integration.expansion_pool import (
        SOURCE_POOL_PATH,
        SOURCE_POOL_SHA256,
        write_adapted_pool,
    )

    pools_dir = Path(run_dir) / "pools"
    pools_dir.mkdir(parents=True, exist_ok=True)
    source = pools_dir / "twin2k_respondent.jsonl"
    if not source.exists():
        if (SOURCE_POOL_PATH.exists()
                and sha256_of(SOURCE_POOL_PATH) == SOURCE_POOL_SHA256):
            shutil.copyfile(SOURCE_POOL_PATH, source)
            log(f"reused canonical Config A pool {SOURCE_POOL_PATH} "
                f"(sha256 verified)")
        else:
            from twin2k10r import serving as pool_serving

            pool_serving.ensure_pool(run_dir, "A", log)
            log("canonical pool unavailable — pool built from the "
                "dataset mirror (seed 42, deterministic)")
    actual = sha256_of(source)
    if actual != SOURCE_POOL_SHA256:
        raise SystemExit(
            f"error: pool sha256 {actual} != pinned "
            f"{SOURCE_POOL_SHA256} — refusing to run on a foreign pool")
    out = pools_dir / "expansion_adapted.jsonl"
    if not out.exists():
        manifest = write_adapted_pool(source, out)
        (pools_dir / "ADAPTED_POOL_MANIFEST.json").write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    adapted = [json.loads(line) for line in
               out.read_text(encoding="utf-8").splitlines() if line.strip()]
    personas = [json.loads(line) for line in
                source.read_text(encoding="utf-8").splitlines()
                if line.strip()]
    if len(personas) != 100 or len(adapted) != 100:
        raise SystemExit(
            f"error: pool holds {len(personas)} records / adapted "
            f"{len(adapted)} — expected 100")
    return personas, adapted


def breakered(scorer, breaker):
    """Wrap one scorer so every call's outcome feeds the circuit breaker."""
    def wrapped(messages):
        raw = scorer(messages)
        if raw.get("succeeded", False):
            breaker.record_success()
        else:
            breaker.record_failure()
            breaker.check()  # raises CircuitOpenError past the cap
        return raw
    return wrapped


def twin_scorers(model: str, base_url: str, breaker):
    """The twin scorers for one model, breakered."""
    from twin2k10r.integration.production import cells_twin

    scorer, digit_scorer = cells_twin.make_scorers(
        model, base_url, cells_twin.merged_stimuli())
    return breakered(scorer, breaker), breakered(digit_scorer, breaker)


def expansion_request_fn(pipeline, model: str, base_url: str, breaker):
    """The expansion request function for one model, breakered."""
    inner = driver_expansion.make_request_fn(pipeline, model, base_url)
    return breakered(inner, breaker)


def leg_counts(personas_n: int) -> dict:
    """The planned cell counts per pipeline (for dry-run and manifest)."""
    twin_total = 0
    specs = run_plan.twin_specs()
    from twin2k10r.integration.production import prompts_twin

    stimuli = prompts_twin.merged_stimuli()
    for experiment in run_plan.twin_experiments():
        arms = specs[experiment].arms
        items_per_arm = sum(
            len(prompts_twin.arm_items(specs[experiment], arm, stimuli))
            for arm, _qids in arms)
        twin_total += 2 * personas_n * items_per_arm  # both blinding arms
    pipeline = driver_expansion.load_pipeline()
    expansion_total = 0
    for exp_id in run_plan.expansion_experiments():
        entry = pipeline.registry.get(exp_id)
        calls_per_persona = sum(
            len(condition.items) for condition in entry.spec.conditions)
        expansion_total += 2 * personas_n * calls_per_persona
    return {
        "twin_calls": twin_total,
        "expansion_calls": expansion_total,
        "personas": personas_n,
        "experiments": len(run_plan.twin_experiments())
        + len(run_plan.expansion_experiments()),
    }


def run_model_block(run_dir, model, personas, adapted, base_url, breaker,
                    pipeline, log, dataset_sha256: str) -> dict:
    """One model's full grid block: twin legs, then expansion legs."""
    done: dict = {"twin": {}, "expansion": {}}
    stimuli = None
    scorers = None
    for experiment in run_plan.twin_experiments():
        for blinded in (True, False):
            key = f"{experiment}_{'blinded' if blinded else 'unblinded'}"
            if scorers is None:
                scorers = twin_scorers(model, base_url, breaker)
            written, total = driver_twin.run_leg(
                run_dir=run_dir, model=model, base_url=base_url,
                experiment=experiment, blinded=blinded, personas=personas,
                run_id=run_dir.name, dataset_sha256=dataset_sha256,
                spec=None, stimuli=stimuli, scorers=scorers,
            )
            done["twin"][key] = {"written": written, "total": total}
            log(f"  {model} twin {key}: +{written} (total {total})")
    request_fn = None
    for exp_id in run_plan.expansion_experiments():
        for blinded in (True, False):
            key = f"{exp_id}_{'blinded' if blinded else 'unblinded'}"
            if request_fn is None:
                request_fn = expansion_request_fn(
                    pipeline, model, base_url, breaker)
            written, total = driver_expansion.run_leg(
                run_dir=run_dir, pipeline=pipeline, model=model,
                base_url=base_url, exp_id=exp_id, blinded=blinded,
                personas=adapted, run_id=run_dir.name,
                dataset_sha256=dataset_sha256,
                request_fn=request_fn,
            )
            done["expansion"][key] = {"written": written, "total": total}
            log(f"  {model} expansion {key}: +{written} (total {total})")
    return done


def write_manifest(run_dir: Path, models: list[str], hashes: dict) -> None:
    """The run manifest's start state (facts fixed before the first call)."""
    payload = {
        "run_id": run_dir.name,
        "study": "twin2k10r-extended-production",
        "config": "A",
        "models": [
            {"record_id": model, "server_id": model_ids.server_model_id(model),
             "flagged": run_plan.is_flagged(model)}
            for model in models
        ],
        "model_order": models,
        "grid": {
            "twin_experiments": list(run_plan.twin_experiments()),
            "expansion_experiments": list(run_plan.expansion_experiments()),
        },
        "inference": {"temperature": 1.0, "top_k": 100, "seed": 42,
                      "logprob_mode": "first_token",
                      "base_url": "http://127.0.0.1:8080"},
        "disclosure": "design+versions only",
        **hashes,
        "started": datetime.now(timezone.utc).isoformat(),
    }
    safeguards.write_atomic_json(run_dir / "manifest.json", payload)


def run(argv=None) -> int:
    """The whole launch: pools, then the model queue, block by block."""
    args = parse_args(argv)
    models = resolve_models(args.models)
    run_dir = args.run_dir or new_run_dir(args.smoke)
    run_dir.mkdir(parents=True, exist_ok=True)
    personas_n = SMOKE_PERSONAS if args.smoke else None

    if args.dry_run:
        pipeline = driver_expansion.load_pipeline()
        from twin2k10r import serving as pool_serving

        pool = pool_serving.ensure_pool(run_dir, "A", log)
        counts = leg_counts(len(pool))
        print(json.dumps({"run_dir": str(run_dir), "models": models,
                          **counts}, indent=2))
        return 0

    hashes = dataset_hashes(run_dir)
    write_manifest(run_dir, models, hashes)
    safeguards.write_pid_file(run_dir)
    personas, adapted = build_pools(run_dir, log)
    hashes = dataset_hashes(run_dir)
    write_manifest(run_dir, models, hashes)  # refresh with pool provenance
    if personas_n is not None:
        personas = personas[:personas_n]
    breaker = safeguards.CircuitBreaker()
    pipeline = driver_expansion.load_pipeline()
    progress = {"records_done": 0, "models_done": [], "per_model": {}}
    safeguards.write_progress(run_dir, progress)
    log(f"run {run_dir.name}: {len(models)} models, {len(personas)} "
        f"personas, 31 experiments, base {args.base_url}")

    from twin2k10r.integration.production import serving_prod

    for model in models:
        safeguards.check_disk(run_dir)
        log(f"=== model {model} "
            f"({model_ids.server_model_id(model)}"
            f"{', FLAGGED' if run_plan.is_flagged(model) else ''}) ===")
        serving_prod.start_model(model, args.base_url, log)
        done = run_model_block(run_dir, model, personas, adapted,
                               args.base_url, breaker, pipeline, log,
                               hashes["dataset_sha256"])
        serving_prod.stop_server()
        progress["models_done"].append(model)
        progress["per_model"][model] = done
        written = sum(block["written"]
                      for leg in done.values()
                      for block in leg.values())
        progress["records_done"] += written
        safeguards.write_progress(run_dir, progress)
    log(f"run complete: {progress['records_done']} records written")
    return 0


def run_smoke(argv=None) -> int:
    """The launch-gate smoke: one model, both pipelines x both arms x
    both scoring types, two personas, into a SMOKE run folder."""
    args = parse_args(argv)
    run_dir = new_run_dir(smoke=True)
    run_dir.mkdir(parents=True, exist_ok=True)
    safeguards.write_pid_file(run_dir)
    personas, adapted = build_pools(run_dir, log)
    hashes = dataset_hashes(run_dir)
    write_manifest(run_dir, [SMOKE_MODEL], hashes)
    personas = personas[:SMOKE_PERSONAS]
    breaker = safeguards.CircuitBreaker()
    pipeline = driver_expansion.load_pipeline()

    from twin2k10r.integration.production import serving_prod

    log(f"SMOKE run {run_dir.name}: {SMOKE_MODEL} on {args.base_url}")
    serving_prod.start_model(SMOKE_MODEL, args.base_url, log)
    scorers = twin_scorers(SMOKE_MODEL, args.base_url, breaker)
    request_fn = expansion_request_fn(pipeline, SMOKE_MODEL, args.base_url,
                                      breaker)
    results: dict = {"twin": {}, "expansion": {}}
    # Both scoring types (choice: disease; digit: sunk_cost) x both arms.
    for experiment in ("disease", "sunk_cost"):
        for blinded in (True, False):
            key = f"{experiment}_{'blinded' if blinded else 'unblinded'}"
            written, total = driver_twin.run_leg(
                run_dir=run_dir, model=SMOKE_MODEL, base_url=args.base_url,
                experiment=experiment, blinded=blinded,
                personas=personas, run_id=run_dir.name,
                dataset_sha256=hashes["dataset_sha256"],
                scorers=scorers)
            results["twin"][key] = {"written": written, "total": total}
            log(f"  twin {key}: +{written} (total {total})")
    # The expansion pipeline, both arms, first grid experiment.
    exp_id = run_plan.expansion_experiments()[0]
    for blinded in (True, False):
        key = f"{exp_id}_{'blinded' if blinded else 'unblinded'}"
        written, total = driver_expansion.run_leg(
            run_dir=run_dir, pipeline=pipeline, model=SMOKE_MODEL,
            base_url=args.base_url, exp_id=exp_id, blinded=blinded,
            personas=adapted[:SMOKE_PERSONAS], run_id=run_dir.name,
            dataset_sha256=hashes["dataset_sha256"],
            request_fn=request_fn)
        results["expansion"][key] = {"written": written, "total": total}
        log(f"  expansion {key}: +{written} (total {total})")
    serving_prod.stop_server()
    safeguards.write_atomic_json(run_dir / "SMOKE_RESULTS.json",
                                 {"run_id": run_dir.name, **results})
    log(f"smoke complete -> {run_dir / 'SMOKE_RESULTS.json'}")
    return 0


def main(argv=None) -> int:
    """Entry point: --smoke takes the rehearsal path, default production."""
    args = parse_args(argv)
    if args.smoke:
        return run_smoke(argv)
    return run(argv)


if __name__ == "__main__":
    raise SystemExit(main())
