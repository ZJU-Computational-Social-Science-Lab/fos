#!/usr/bin/env python3
"""Interim/final results report for a Gui & Toubia launch run (R1 profile).

This tool is READ-ONLY: it turns a launch run directory (the kind
scripts/launch_grid.py creates, e.g. results/unblinding/R1-*) into a
human readable report the moment any sweep leg record lands, and it can
also be run while the sweep is still in flight (it simply reports
whatever is on disk, including "no sweep records yet"). It never writes
into the run directory and never touches the Twin-2K-500 dataset: the
only files it creates are the report and its optional JSON twin.

What it computes, per (depth x blinding) condition found on disk:

  * Parse rate under two labels: STRICT (the tooling's own parse_purchase
    applied to each record's raw answer) and RECOVERED (strict plus a
    re-parse pass that rescues the documented pilot failure mode - a valid
    first decision followed by a trailing comma-list echo, e.g.
    "not purchase,not purchase,0.00,30,6,"). p(buy) is reported under both
    labels.
  * p(buy) per price level pooled across products, with Wilson 95%
    confidence intervals, plus a per-product p(buy) matrix.
  * A human benchmark join when the Twin-2K-500 dataset is available:
    MAE(model, human) per condition (mean over product x price cells of
    |p_model - p_human|, the paper's way) and pooled-average comparisons.
    If the dataset path is missing the benchmark section is skipped with a
    clear note.

The numeric work lives in three sibling modules (the same split the
launch_* wrapper uses): r1_interim_analysis.py (parsing, cells, curves,
comparisons), r1_interim_benchmark.py (reading the Twin-2K-500 dataset)
and r1_interim_render.py (markdown + JSON rendering). This file owns the
command line, the read-only file discovery, and the report's assembly.

Function map (plain language):
    _parse_args              Read the command-line switches.
    _run_dir_to_use          Pick the run dir: --run-dir or the newest R1-*.
    _products_file_to_use    Pick the products file: --products-file, the
                             run manifest's, or the repo default.
    _resolve_path            The path itself or the same path under the repo
                             root, whichever exists.
    _load_json / _load_products  Read one JSON file / the products list.
    _read_leg_records        Read every jsonl record of one leg folder.
    _discover_leg_dirs       List the <depth>_<blinding> folders of a run.
    _pools_note              One line about the run's persona pool phase.
    _order_legs              Sort legs into a stable report order.
    _decide_and_summarise    Parse + summarise one leg's records.
    _make_header             The provenance block both outputs share.
    _atomic_write            Write a file so no partial report ever remains.
    main                     Tie everything together and pick the exit code.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parent
for _dir in (_SCRIPT_DIR, _REPO_ROOT / "src"):
    if str(_dir) not in sys.path:
        sys.path.insert(0, str(_dir))

from r1_interim_analysis import (  # noqa: E402
    compare_condition,
    condition_summary,
    decide_records,
)
from r1_interim_benchmark import (  # noqa: E402
    benchmark_available,
    build_human_table,
)
from r1_interim_render import (  # noqa: E402
    analysis_json,
    condition_markdown,
    render_json,
    render_markdown,
)

DEFAULT_OUT_ROOT = "results/unblinding"
DEFAULT_PRODUCTS = "data/configs/unblinding_products.json"
DEFAULT_TWIN_DIR = Path("/home/justin/work/datasets/Twin-2K-500")
_DEPTH_ORDER = ["none", "demographics"]


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    """Read the command-line switches into one options object."""
    parser = argparse.ArgumentParser(
        prog="r1_interim_report",
        description=(
            "Read-only interim/final results report for a launch run dir "
            "(scripts/launch_grid.py layout)."
        ),
    )
    parser.add_argument(
        "--run-dir",
        default="",
        help="run directory to report on (default: the newest "
        "results/unblinding/R1-* next to the repo)",
    )
    parser.add_argument(
        "--out",
        default="",
        help="report file path (default: <run dir's parent>/<run "
        "name>.interim-report.md)",
    )
    parser.add_argument(
        "--products-file",
        default="",
        help="products json (default: the run manifest's products_file, "
        "then the repo default)",
    )
    parser.add_argument(
        "--twin-dir",
        default=str(DEFAULT_TWIN_DIR),
        help="Twin-2K-500 dataset directory (default: %(default)s)",
    )
    parser.add_argument(
        "--json", action="store_true", help="also write a JSON twin of the report"
    )
    return parser.parse_args(argv)


def _run_dir_to_use(arg: str) -> Path:
    """Pick the run directory: --run-dir, or the newest R1-* on disk."""
    if arg:
        return Path(arg)
    newest: Path | None = None
    for base in (Path("results/unblinding"), _REPO_ROOT / DEFAULT_OUT_ROOT):
        if not base.is_dir():
            continue
        for folder in base.glob("R1-*"):
            if folder.is_dir() and (newest is None or folder.name > newest.name):
                newest = folder
    if newest is None:
        print(
            "error: no results/unblinding/R1-* run directory found near the "
            "repo; pass --run-dir",
            file=sys.stderr,
        )
        raise SystemExit(2)
    return newest


def _products_file_to_use(manifest: dict[str, Any] | None, arg: str) -> Path | None:
    """Pick the products file: --products-file, the manifest's, or default."""
    if arg:
        return Path(arg)
    hinted = (manifest or {}).get("products_file")
    if isinstance(hinted, str) and hinted:
        return Path(hinted)
    return _REPO_ROOT / DEFAULT_PRODUCTS


def _resolve_path(path: Path) -> Path | None:
    """The path itself or the same path under the repo root, if it exists."""
    if path.exists():
        return path
    candidate = _REPO_ROOT / path
    return candidate if candidate.exists() else None


def _load_json(path: Path) -> Any:
    """Read one JSON file (raises the natural OSError on failure)."""
    return json.loads(path.read_text(encoding="utf-8"))


def _load_products(path: Path | None) -> list[dict[str, Any]]:
    """Read the products list, accepting either top-level JSON shape."""
    if path is None:
        return []
    resolved = _resolve_path(path)
    if resolved is None:
        return []
    payload = _load_json(resolved)
    products = payload if isinstance(payload, list) else payload.get("products", [])
    return [p for p in products if isinstance(p, dict) and p.get("product")]


def _read_leg_records(
    leg_dir: Path,
) -> tuple[list[dict[str, Any]], int, list[str]]:
    """Read every jsonl record of one leg folder.

    Returns (records, torn, files): the parsed records, the number of lines
    that were not valid JSON (counted, never silently dropped), and the
    jsonl files read. A leg that is still running has no records yet, so an
    empty list is a normal, expected result.
    """
    files = sorted(str(path) for path in leg_dir.glob("*.jsonl"))
    records: list[dict[str, Any]] = []
    torn = 0
    for name in files:
        with Path(name).open(encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                try:
                    parsed = json.loads(line)
                except json.JSONDecodeError:
                    torn += 1
                    continue
                if isinstance(parsed, dict):
                    records.append(parsed)
    return records, torn, files


def _discover_leg_dirs(run_dir: Path) -> list[dict[str, Any]]:
    """List the (depth x blinding) leg folders of a run directory.

    launch_sweep writes each leg into <run>/<depth>_<blinding>/. Any folder
    whose name ends in _blinded or _unblinded counts (pools folders do not
    match, so they are naturally skipped). Missing leg folders simply do
    not appear; a folder that exists but has no records yet appears with an
    empty record list so an in-flight run is reported honestly.
    """
    legs: list[dict[str, Any]] = []
    if not run_dir.is_dir():
        return legs
    for folder in sorted(run_dir.iterdir()):
        if not folder.is_dir():
            continue
        if not folder.name.endswith(("_blinded", "_unblinded")):
            continue
        depth, blinding = folder.name.rsplit("_", 1)
        records, torn, files = _read_leg_records(folder)
        legs.append(
            {
                "depth": depth,
                "blinding": blinding,
                "dir": folder,
                "records": records,
                "torn": torn,
                "files": files,
            }
        )
    return legs


def _order_legs(legs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sort legs into a stable order: depth tiers, then blinding."""
    return sorted(
        legs,
        key=lambda leg: (
            _DEPTH_ORDER.index(leg["depth"])
            if leg["depth"] in _DEPTH_ORDER
            else len(_DEPTH_ORDER),
            leg["blinding"],
        ),
    )


def _pools_note(run_dir: Path) -> str:
    """One-line summary of the run's persona pool phase, or a dash."""
    pools = run_dir / "pools.json"
    if not pools.exists():
        return "-"
    payload = _load_json(pools)
    accepted = payload.get("accepted_total")
    if accepted is None:
        return "pools.json present"
    return (
        f"{accepted}/{payload.get('requested')} accepted personas "
        f"(seed {payload.get('pool_seed')}, "
        f"{payload.get('products')} products)"
    )


def _make_header(
    run_dir: Path,
    manifest: dict[str, Any],
    levels: list[float],
    decided: list[dict[str, Any]],
    torn: int,
    human_note: str,
) -> dict[str, Any]:
    """The provenance block that both the markdown and JSON share."""
    strict_parsed = sum(1 for r in decided if r["strict"] is not None)
    recovered_parsed = sum(1 for r in decided if r["recovered"] is not None)
    recovered_only = recovered_parsed - strict_parsed
    total = len(decided)
    return {
        "run_name": manifest.get("run_name") or run_dir.name,
        "run_dir": str(run_dir),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "run_state": manifest.get("state", "unknown"),
        "model": manifest.get("model", ""),
        "commit_sha": manifest.get("commit_sha"),
        "levels": levels,
        "draws": manifest.get("draws"),
        "k": manifest.get("k"),
        "seed": manifest.get("seed"),
        "pool_seed": manifest.get("pool_seed"),
        "profile": manifest.get("profile"),
        "records": total,
        "torn": torn,
        "strict_parsed": strict_parsed,
        "strict_rate": strict_parsed / total if total else 0.0,
        "recovered_parsed": recovered_parsed,
        "recovered_rate": recovered_parsed / total if total else 0.0,
        "recovered_only": recovered_only,
        "pools": _pools_note(run_dir),
        "benchmark_note": human_note,
    }


def _atomic_write(path: Path, content: str) -> None:
    """Write content so no partial report is ever left on disk."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with open(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
        Path(temp_name).replace(path)
    finally:
        Path(temp_name).unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    """Tie the whole report together and pick the exit code.

    The run directory and the Twin dataset are only ever read. The report
    is written atomically next to the run directory (never inside it).
    Exit code 0 means the report was written (even with no sweep records
    yet); exit code 2 means the run directory could not be found.
    """
    args = _parse_args(argv)
    run_dir = _run_dir_to_use(args.run_dir)
    manifest: dict[str, Any] = {}
    try:
        manifest = _load_json(run_dir / "manifest.json")
    except FileNotFoundError:
        print(
            f"note: {run_dir}/manifest.json not found; continuing from the "
            "records on disk",
            file=sys.stderr,
        )
    legs = _order_legs(_discover_leg_dirs(run_dir))
    decided = [record for leg in legs for record in decide_records(leg["records"])]
    levels = _levels_for(manifest, decided)
    torn = sum(leg["torn"] for leg in legs)
    human_table, human_note = _load_human_table(args, manifest)
    header = _make_header(run_dir, manifest, levels, decided, torn, human_note)
    sections, sections_json = _report_parts(legs, levels, human_table)
    markdown = render_markdown(header, sections)
    if not sections:
        markdown += (
            "\nNo <depth>_<blinding> leg folders found on disk yet — the "
            "sweep has not started writing legs.\n"
        )
    out_path = (
        Path(args.out)
        if args.out
        else run_dir.parent / f"{run_dir.name}.interim-report.md"
    )
    _atomic_write(out_path, markdown)
    print(f"wrote {out_path}")
    if args.json:
        _atomic_write(
            out_path.with_suffix(".json"),
            json.dumps(render_json(header, sections_json), indent=2) + "\n",
        )
        print(f"wrote {out_path.with_suffix('.json')}")
    return 0


def _levels_for(manifest: dict[str, Any], decided: list[dict[str, Any]]) -> list[float]:
    """The report's price levels: the manifest's, else the records' own."""
    levels = sorted(float(level) for level in (manifest.get("levels") or []))
    if levels:
        return levels
    return sorted(
        {
            float(record.get("treatment_value", 0.0))
            for record in decided
            if record.get("treatment_value") is not None
        }
    ) or [0.0]


def _load_human_table(
    args: argparse.Namespace, manifest: dict[str, Any]
) -> tuple[dict[str, Any] | None, str]:
    """Build the benchmark table when possible; else (None, why-not note).

    The note lands in the report's provenance header, so a skipped or
    partial benchmark is always visible instead of silently absent.
    """
    products_file = _products_file_to_use(manifest, args.products_file)
    products = _load_products(products_file)
    ok, reason = benchmark_available(Path(args.twin_dir))
    if not ok:
        return None, f"benchmark skipped: {reason}"
    if not products:
        return None, (
            "benchmark skipped: no products file found, so the dataset "
            "prices cannot be placed on the level grid"
        )
    human, note = build_human_table(Path(args.twin_dir), products)
    print(
        f"benchmark: {human['pids']:,} participants, "
        f"{human['responses']:,} pricing responses in the join"
    )
    return human, f"used ({note})"


def _report_parts(
    legs: list[dict[str, Any]],
    levels: list[float],
    human_table: dict[str, Any] | None,
) -> tuple[list[list[str]], list[dict[str, Any]]]:
    """Build the markdown sections and JSON twins of every condition."""
    sections: list[list[str]] = []
    sections_json: list[dict[str, Any]] = []
    for leg in legs:
        decided = decide_records(leg["records"])
        summary = condition_summary(decided, levels) if leg["records"] else None
        comparison = None
        if summary is not None and human_table is not None:
            comparison = compare_condition(summary, human_table)
        sections.append(condition_markdown(leg, summary, levels, comparison))
        sections_json.append(analysis_json(leg, summary, comparison))
    return sections, sections_json


if __name__ == "__main__":
    raise SystemExit(main())
