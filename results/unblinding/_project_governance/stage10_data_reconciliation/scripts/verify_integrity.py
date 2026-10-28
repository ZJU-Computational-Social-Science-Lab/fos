# verify_integrity.py — re-verifies the promoted canonical build against
# its provenance manifest: recomputes every SHA-256 (inputs and outputs,
# project-relative paths), checks the registry pointer, and re-runs the
# schema/key checks. Exit code 0 = verified; anything else fails loudly.
#
# What each function does:
#   verify           — full check, prints a pass/fail line per item.
#   main             — CLI entry (python verify_integrity.py).

from __future__ import annotations

import json
import sys
from pathlib import Path

from stage10_common import (DATA_DIR, MANIFEST, REGISTRY_JSON, UNBL, VERSION,
                            sha256_file)
import canonical_data


def verify() -> list[tuple[str, bool, str]]:
    """Every integrity check with a pass/fail flag and detail."""
    results: list[tuple[str, bool, str]] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        results.append((name, ok, detail))

    if not MANIFEST.is_file():
        check("manifest-present", False, str(MANIFEST))
        return results
    manifest = json.loads(MANIFEST.read_text())
    check("manifest-version", manifest.get("version") == VERSION,
          str(manifest.get("version")))

    bad = []
    for rel, recorded in manifest.get("inputs", {}).items():
        path = Path(rel)
        if not path.is_file():
            bad.append(f"{rel}: missing")
        elif sha256_file(path) != recorded:
            bad.append(f"{rel}: hash changed")
    check("input-hashes", not bad, "; ".join(bad[:5]))

    bad = []
    for name, recorded in manifest.get("outputs", {}).items():
        path = DATA_DIR / name
        if not path.is_file():
            bad.append(f"{name}: missing")
        elif sha256_file(path) != recorded:
            bad.append(f"{name}: hash changed")
    check("output-hashes", not bad, "; ".join(bad[:5]))

    registry = json.loads(REGISTRY_JSON.read_text())
    check("registry-approved", registry.get("approved") == VERSION,
          str(registry.get("approved")))
    entry = registry["versions"][VERSION]
    check("registry-manifest-hash",
          entry.get("manifest_sha256") == sha256_file(MANIFEST))

    for table in ("arm_outcomes", "model_effects", "uncertainty", "paired"):
        try:
            canonical_data.load_table(table)
            check(f"schema-{table}", True)
        except canonical_data.CanonicalDataError as exc:
            check(f"schema-{table}", False, str(exc))
    return results


def main() -> int:
    """CLI entry: print results, exit non-zero on any failure."""
    failures = 0
    for name, ok, detail in verify():
        print(f"{'PASS' if ok else 'FAIL'}  {name}"
              + (f"  ({detail})" if detail and not ok else ""))
        failures += 0 if ok else 1
    print(f"verify_integrity: {'ALL CHECKS PASS' if not failures else
          f'{failures} FAILURES'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
