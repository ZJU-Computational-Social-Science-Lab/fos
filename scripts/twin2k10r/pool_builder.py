# This file picks the respondents and turns them into persona records.
# Sampling is fully deterministic: stratified proportional allocation on
# gender x age bracket with the largest-remainder rule, drawn without
# replacement by numpy's PCG64 generator seeded 42, strata and people
# always walked in sorted order. The same inputs therefore always give
# the same 100 people. Functions:
#   sample_respondents — the sorted pid list of the sampled people.
#   sample_respondents_from_provenance — replay the exact same draw from
#                        a saved provenance record (used for auditing).
#   map_fields         — one person -> their whitelisted persona dict.
#   write_pool         — write the pool JSONL + POOL_PROVENANCE.json and
#                        return the provenance record.
import hashlib
import json
import subprocess
from pathlib import Path

import numpy as np

from twin2k10r import config, dataset_manifest, respondent_loader

# The stratification the study uses (sex x age bracket).
DEFAULT_STRATA = ("gender", "age_bracket")

# The 4 fields the original synthetic study rendered but the real dataset
# cannot provide, with the honest reason each is omitted (from
# CORRECTED_DESIGN §2.2). These reasons travel in every provenance record.
EXCLUDED_FIELD_REASONS = {
    "occupation": (
        "not collected; QID24 employment status is not a job title and "
        "deriving one would fabricate data"
    ),
    "number_of_children": (
        "not collected; household size includes adults, so a count would "
        "be fabricated"
    ),
    "state": (
        "not collected; QID11 holds 5 Census regions, not states, and "
        "rendering a region as a state would mislabel it"
    ),
    "home_ownership": (
        "not collected in any wave"
    ),
}

RNG_ALGORITHM = "numpy PCG64"


def _stratify(respondents, strata):
    """Group panel pids by stratum, all keys sorted, pids sorted inside."""
    ordered = respondents.sort_values("pid")
    grouped = {}
    for key, group in ordered.groupby(list(strata), sort=True):
        grouped[key] = sorted(int(pid) for pid in group["pid"])
    return grouped


def _largest_remainder(allocation_shares, total_seats):
    """Split total_seats across strata proportionally, remainder to the
    largest fractional leftovers (ties broken by sorted key order)."""
    exact = {key: share * total_seats for key, share in allocation_shares.items()}
    seats = {key: int(value) for key, value in exact.items()}
    leftovers = total_seats - sum(seats.values())
    order = sorted(exact, key=lambda key: (-(exact[key] - seats[key]), key))
    for key in order[:leftovers]:
        seats[key] += 1
    return seats


def _draw(stratum_pids, allocation, seed):
    """Draw each stratum's seats without replacement, strata in sorted
    key order, one shared PCG64 generator. This exact walk is what the
    provenance replay must reproduce step for step."""
    rng = np.random.default_rng(seed)
    picked = []
    for key in sorted(stratum_pids):
        members = np.asarray(stratum_pids[key], dtype=np.int64)
        seats = allocation[key]
        if seats > len(members):
            raise ValueError(
                f"stratum {key!r} needs {seats} people but holds only "
                f"{len(members)} — sampling without replacement is impossible"
            )
        chosen = rng.choice(members, size=seats, replace=False)
        picked.extend(int(pid) for pid in chosen)
    return sorted(picked)


def sample_respondents(respondents, n: int = config.PERSONA_COUNT,
                       seed: int = config.SEED,
                       strata: tuple = DEFAULT_STRATA) -> list:
    """The deterministic stratified sample.

    In: the respondent table, the wanted size, the seed, the stratum
    columns. Out: ascending sorted pid list of length n. Same inputs ->
    identical output, every time.
    """
    grouped = _stratify(respondents, strata)
    panel_total = sum(len(members) for members in grouped.values())
    if n > panel_total:
        raise ValueError(
            f"asked for {n} people but the panel holds only {panel_total}"
        )
    shares = {key: len(members) / panel_total
              for key, members in grouped.items()}
    allocation = _largest_remainder(shares, n)
    return _draw(grouped, allocation, seed)


def sample_respondents_from_provenance(provenance, dataset_root=None) -> list:
    """Replay the sample from a provenance record alone.

    In: the provenance dict (and optionally a dataset root, unused — the
    record already carries each stratum's full membership). Out: the same
    sorted pid list the original run drew, byte-for-byte reproducible in
    a fresh process.
    """
    return _draw(provenance["stratum_pids"], provenance["allocation"],
                 provenance["seed"])


def map_fields(pid: int, respondents, config_id: str,
               extra_fields: tuple = ()) -> dict:
    """One respondent -> their persona dict.

    In: one pid, the respondent table, the config id. Out: a dict with
    exactly the whitelisted keys (string values, the dataset's own label
    text). Unavailable fields are absent keys — never placeholders, never
    derived, never invented. Unknown configs or blocklisted extra fields
    raise UnknownFieldError.
    """
    whitelist = respondent_loader.get_field_whitelist(config_id)
    for field in extra_fields:
        if field in respondent_loader.SCORE_BLOCKLIST or field not in whitelist:
            raise respondent_loader.UnknownFieldError(
                f"{field} is not renderable under config {config_id!r}"
            )
    rows = respondents[respondents["pid"] == pid]
    if rows.empty:
        raise ValueError(f"pid {pid} is not in the respondent table")
    row = rows.iloc[0]
    return {field: str(row[field]) for field in whitelist}


def _pipeline_git_sha() -> str:
    """The pipeline's git commit, recorded for the provenance chain.
    Returns "unknown" when git cannot answer (e.g. a read-only .git)."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True,
            timeout=10, check=True,
        )
        return result.stdout.strip()
    except Exception as exc:
        print(f"warning: could not record git sha: {exc}")
        return "unknown"


def write_pool(pids: list, respondents, config_id: str, out_path) -> dict:
    """Write the pool JSONL and its provenance record.

    In: the sampled pid list (line order = pool id 0..n-1), the table,
    the config id, the output path (pools/twin2k_respondent.jsonl).
    Out: the provenance dict, also written as POOL_PROVENANCE.json next
    to the pool. Idempotent: identical inputs give byte-identical files.
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    for pool_id, pid in enumerate(pids):
        record = {"pool_id": pool_id, "pid": pid,
                  **map_fields(pid, respondents, config_id)}
        lines.append(json.dumps(record, sort_keys=True, ensure_ascii=True))
    pool_text = "\n".join(lines) + "\n"
    out_path.write_text(pool_text, encoding="utf-8")

    grouped = _stratify(respondents, DEFAULT_STRATA)
    counts = {str(key): 0 for key in grouped}
    for pid in pids:
        for key, members in grouped.items():
            if pid in members:
                counts[str(key)] += 1
                break
    whitelist = respondent_loader.get_field_whitelist(config_id)
    provenance = {
        "seed": config.SEED,
        "rng_algorithm": RNG_ALGORITHM,
        "n": len(pids),
        "config_id": config_id,
        "strata": list(DEFAULT_STRATA),
        "pid": sorted(int(pid) for pid in pids),
        "allocation": counts,
        "stratum_pids": {str(key): members
                         for key, members in grouped.items()},
        "pool_sha256": hashlib.sha256(pool_text.encode("utf-8")).hexdigest(),
        "dataset_manifest_sha256": dataset_manifest.manifest_sha256(
            config.DATASET_ROOT
        ),
        "pipeline_git_sha": _pipeline_git_sha(),
        "field_whitelist": list(whitelist),
        "excluded_fields": dict(EXCLUDED_FIELD_REASONS),
    }
    provenance_path = out_path.parent / "POOL_PROVENANCE.json"
    provenance_path.write_text(
        json.dumps(provenance, indent=2, sort_keys=True, ensure_ascii=True)
        + "\n",
        encoding="utf-8",
    )
    return provenance
