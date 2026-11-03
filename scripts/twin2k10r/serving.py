# This file is the twin2k10r pool plumbing: it makes sure every run has
# its shared persona pool, and loads that pool back with hard checks.
# The persona path contains zero model calls — building the pool is pure
# data loading from the dataset mirror. Functions:
#   ensure_pool — return the run's pool, building it once if needed and
#                 recording the provenance that gates every later step.
#   load_pool   — read the pool JSONL back, refusing a wrong size or any
#                 leaking field.
import hashlib
import json
from pathlib import Path

from twin2k10r import config, dataset_manifest, pool_builder, respondent_loader

# One pool file name per run, same convention as the existing studies.
POOL_FILENAME = "twin2k_respondent.jsonl"
PROVENANCE_FILENAME = "POOL_PROVENANCE.json"


def _pool_path(run_dir) -> Path:
    """Where the run's pool JSONL lives."""
    return Path(run_dir) / "pools" / POOL_FILENAME


def _provenance_path(run_dir) -> Path:
    """Where the run's pool provenance record lives."""
    return Path(run_dir) / "pools" / PROVENANCE_FILENAME


def load_pool(run_dir) -> list:
    """The shared persona pool: 100 personas, ids 0-99 in line order.

    Refuses loudly a pool with the wrong size or any field outside the
    whitelist recorded in the run's own provenance — a polluted pool
    would leak into every prompt of every model.
    """
    provenance = json.loads(_provenance_path(run_dir).read_text("utf-8"))
    whitelist = set(provenance["field_whitelist"])
    personas = [
        json.loads(line)
        for line in _pool_path(run_dir).read_text("utf-8").splitlines()
        if line.strip()
    ]
    if len(personas) != config.PERSONA_COUNT:
        raise SystemExit(
            f"error: {_pool_path(run_dir)} holds {len(personas)} personas, "
            f"expected {config.PERSONA_COUNT}"
        )
    for index, persona in enumerate(personas):
        extra = {key for key in persona
                 if key not in whitelist and key not in ("pid", "pool_id")}
        if extra:
            raise SystemExit(
                f"error: persona {index} carries non-whitelisted fields "
                f"{sorted(extra)} — refusing a leaking pool"
            )
    return personas


def ensure_pool(run_dir, config_id: str, log) -> list:
    """The pool phase, with no model anywhere in it.

    If the run already has a pool whose sha256 matches its provenance,
    it is loaded back as-is (idempotent). Otherwise the pool is built
    from the dataset mirror: fingerprint-check the dataset, load the
    verified respondent table, draw the deterministic stratified sample,
    and write pool + provenance. Returns the 100 personas.
    """
    provenance_path = _provenance_path(run_dir)
    pool_path = _pool_path(run_dir)
    if provenance_path.exists() and pool_path.exists():
        provenance = json.loads(provenance_path.read_text("utf-8"))
        actual = hashlib.sha256(pool_path.read_bytes()).hexdigest()
        if provenance.get("pool_sha256") == actual:
            log(f"pool already built ({actual[:12]}...) — reusing it")
            return load_pool(run_dir)
        log("pool file does not match its provenance — rebuilding")

    manifest_file = _provenance_path(run_dir).parent / "dataset_manifest.json"
    manifest_file.parent.mkdir(parents=True, exist_ok=True)
    if not manifest_file.exists():
        dataset_manifest.write_manifest(config.DATASET_ROOT, manifest_file)
    dataset_manifest.verify_manifest(config.DATASET_ROOT, manifest_file)
    log(f"loading respondents from {config.DATASET_ROOT} (config {config_id})")
    respondents = respondent_loader.load_respondents(
        config.DATASET_ROOT, config_id
    )
    pids = pool_builder.sample_respondents(
        respondents, n=config.PERSONA_COUNT, seed=config.SEED
    )
    provenance = pool_builder.write_pool(
        pids, respondents, config_id, pool_path
    )
    log(f"built pool of {len(pids)} from pids "
        f"{pids[:3]}... (sha256 {provenance['pool_sha256'][:12]}...)")
    return load_pool(run_dir)
