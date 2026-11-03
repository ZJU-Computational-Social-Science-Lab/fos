# This module adapts the real-respondent persona pool (Config A, the
# twin2k10r Stage 0 pool of 100 real Twin-2K-500 panel members) so the
# frozen expansion pipeline can load it without any change to that
# pipeline. The expansion loader only accepts the 11 legacy demographic
# field names and rejects any other key, while the real pool uses the
# dataset's own names (age_bracket, household_income_bracket,
# household_size_bracket) and carries two bookkeeping keys (pid,
# pool_id). The adapter renames the three fields, drops the two
# bookkeeping keys, keeps every value byte-identical (the bracket
# strings ARE the measured data — converting them would fabricate), and
# preserves record order so persona_id (the position in the file) keeps
# pointing at the same respondent it points at in twin2k10r.
# Functions:
#   adapt_twin2k10r_pool — read the pool file, return the adapted personas.
#   write_adapted_pool   — write the adapted pool to a NEW jsonl file and
#                          return a provenance manifest (hashes, counts).
#   load_expansion_pipeline — read-only import helper for the frozen
#                          expansion pipeline (never modifies it).
#   expansion_personas   — adapt a pool and hand it to the expansion
#                          loader's format check without touching anything.
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

# The three dataset field names and the legacy names the expansion
# pipeline expects. Values pass through untouched.
FIELD_RENAMES = {
    "age_bracket": "age",
    "household_income_bracket": "household_income",
    "household_size_bracket": "household_size",
}

# Bookkeeping keys that must never reach a prompt. The respondent id is
# recorded once in the provenance manifest instead of per record.
DROPPED_KEYS = ("pid", "pool_id")

# The 7 real demographic answers every Config A record must carry
# (dataset names, before renaming).
REQUIRED_SOURCE_FIELDS = frozenset(
    {"age_bracket", "gender", "education", "household_income_bracket",
     "ethnicity", "marital_status", "household_size_bracket"}
)

# Pool size the expansion pipeline hard-requires.
PERSONA_COUNT = 100

# The canonical Stage 0 Config A pool (hash-pinned; never overwritten).
SOURCE_POOL_PATH = Path(
    "/home/justin/Documents/ZJU work/fos/results/unblinding/"
    "twin2k_redesign/stage0/pools/twin2k_respondent.jsonl"
)
SOURCE_POOL_SHA256 = (
    "bdc842334a71aa61f20797f778d77cad1eefd772dec08e4498d4e357f447eea1"
)

# The frozen expansion pipeline lives outside this repository copy; it is
# imported read-only and never edited here.
EXPANSION_PIPELINE_DIR = Path(
    "/home/justin/Documents/ZJU work/fos/results/unblinding/expansion/pipeline"
)


class PoolShapeError(ValueError):
    """The pool file does not hold exactly the required number of records."""


class PoolFieldError(ValueError):
    """A record carries an unknown key, or misses/blank-blanks a real field."""


class PoolValueError(ValueError):
    """A field value is empty or not a plain string worth rendering."""


def _sha256_of(path: Path) -> str:
    """The file's SHA-256, read in chunks so pool size never matters."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _adapt_record(record: dict, index: int) -> dict:
    """One source record -> one expansion-shaped persona dict.

    Raises PoolFieldError on unknown keys or missing/blank required
    fields, PoolValueError on a non-string value where one is required.
    """
    unknown = set(record) - REQUIRED_SOURCE_FIELDS - set(DROPPED_KEYS)
    if unknown:
        raise PoolFieldError(
            f"persona {index} carries unknown keys {sorted(unknown)}"
        )
    missing = REQUIRED_SOURCE_FIELDS - set(record)
    if missing:
        raise PoolFieldError(
            f"persona {index} is missing required fields {sorted(missing)}"
        )
    persona: dict = {}
    for key, value in record.items():
        if key in DROPPED_KEYS:
            continue
        if not isinstance(value, str) or not value.strip():
            raise PoolValueError(
                f"persona {index} field {key!r} is empty or not a string"
            )
        persona[FIELD_RENAMES.get(key, key)] = value
    return persona


def adapt_twin2k10r_pool(pool_path: Path) -> list[dict]:
    """The whole pool, adapted: pure, order-preserving, deterministic.

    Raises PoolShapeError when the record count is not exactly
    PERSONA_COUNT; per-record errors as in _adapt_record.
    """
    records = []
    for line in pool_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            records.append(json.loads(line))
    if len(records) != PERSONA_COUNT:
        raise PoolShapeError(
            f"{pool_path} holds {len(records)} records, "
            f"expected {PERSONA_COUNT}"
        )
    return [_adapt_record(record, i) for i, record in enumerate(records)]


def write_adapted_pool(pool_path: Path, out_path: Path) -> dict:
    """Write the adapted pool to a NEW file; return the run manifest.

    Refuses to overwrite anything (the adapted pool is a new artifact;
    the source pool and the historical synthetic pool are never touched).
    """
    if out_path.exists():
        raise FileExistsError(
            f"refusing to overwrite {out_path} — adapted pools are "
            "write-once artifacts"
        )
    source_sha = _sha256_of(pool_path)
    personas = adapt_twin2k10r_pool(pool_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as handle:
        for persona in personas:
            handle.write(
                json.dumps(persona, sort_keys=True, ensure_ascii=False)
                + "\n"
            )
    return {
        "source_sha256": source_sha,
        "adapted_sha256": _sha256_of(out_path),
        "n": len(personas),
        "renames": dict(FIELD_RENAMES),
        "dropped_keys": list(DROPPED_KEYS),
    }


def load_expansion_pipeline():
    """Import the frozen expansion pipeline read-only and return it.

    Inserts the pipeline's parent directory on sys.path (its modules
    import each other as `pipeline.*`) without touching the repository
    or the pipeline files themselves.
    """
    parent = str(EXPANSION_PIPELINE_DIR.parent)
    if parent not in sys.path:
        sys.path.insert(0, parent)
    import pipeline.config  # noqa: F401  (read-only import)
    import pipeline.prompts
    import pipeline.registry
    import pipeline.runner
    return sys.modules["pipeline"]


def expansion_personas(pool_path: Path):
    """Adapt the pool and verify it against the expansion loader's rules.

    Returns (pipeline package, adapted personas). The personas' key sets
    are strict subsets of pipeline.prompts.PERSONA_FIELDS and the count
    matches pipeline.config.PERSONA_COUNT, so the pipeline's own
    load_personas() accepts the file unchanged.
    """
    pipeline = load_expansion_pipeline()
    personas = adapt_twin2k10r_pool(pool_path)
    allowed = set(pipeline.prompts.PERSONA_FIELDS)
    if len(personas) != pipeline.config.PERSONA_COUNT:
        raise PoolShapeError(
            f"adapted pool holds {len(personas)} personas, the expansion "
            f"pipeline requires {pipeline.config.PERSONA_COUNT}"
        )
    for index, persona in enumerate(personas):
        extra = set(persona) - allowed
        if extra:
            raise PoolFieldError(
                f"persona {index} still carries non-demographic fields "
                f"{sorted(extra)} after adaptation"
            )
    return pipeline, personas
