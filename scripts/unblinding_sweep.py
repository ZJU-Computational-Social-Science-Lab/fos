"""Run the unblinding price-sweep experiment against a local chat server.

This script drives the demand sweep described in the Gui & Toubia-style
unblinding comparison. It asks an LLM chat server how likely it is to buy a
product at many price levels, under a blinded condition (the model never
learns prices are randomized) and/or an unblinded condition (the model is
told the design). Everything needed to run lives in fos.experiments.sweep_kit;
this script only talks to the network, saves the results, and prints the
demand and confounding tables.

What each function does:
    main(argv)                    - The entry point: parse flags, check the
                                    server, run every requested blinding, save
                                    results, write the manifest.
    _parse_args(argv)             - Turn command-line flags into a settings
                                    object (see the flag help text).
    _scope_for(blinding)          - Turn "blinded"/"unblinded"/"both" into the
                                    list of blinding runs to do.
    _safe_model_name(model)       - Make a model id safe to use in a file name.
    _parse_levels(text)           - Read a comma list of price percentages.
    _parse_covariates(text)       - Read a comma list of covariate kinds.
    _load_products(path)          - Read the products file (either shape).
    _resolve_products_path(value) - Find the products file, also relative to
                                    the repository root.
    _build_design(...)            - Build the price randomization design.
    _server_root(base_url)        - Normalize a server address for joining.
    _post_json(url, payload, ...) - POST JSON and return (status, body).
    _get(url, timeout)            - GET a url and return (status, body).
    build_sweep_chat_fn(...)      - Build the chat function the sweep kit
                                    calls; one retry, "" on final failure.
    _probe(url, timeout)          - Check a server answers; error text or None.
    _switch_model(...)            - Ask the manager to load a model on a port.
    _wait_until_healthy(...)      - Poll the health endpoint until it passes.
    _is_healthy_status(body)      - Does a health body mean "healthy"?
    _write_records(base, records) - Save records to base.jsonl and base.csv.
    _csv_cell(value)              - Make one record value CSV-safe.
    _print_demand_table(...)      - Print the level / n / p_buy demand curve.
    _run_diagnostic(...)          - Run the confounding diagnostic, print and
                                    save the rho / CI / flag summary.
    _print_diagnostic_table(...)  - Print one confounding summary table.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

# Make this worktree's `src` importable when the script runs directly.
_REPO_ROOT = Path(__file__).resolve().parent.parent
_SRC_DIR = _REPO_ROOT / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from fos.experiments.randomization import RandomizationDesign  # noqa: E402
from fos.experiments.sweep_kit import (  # noqa: E402
    aggregate_demand,
    run_diagnostic,
    run_sweep,
    summarize_confounding,
    write_manifest,
)

# Command-line defaults (see the task spec).
DEFAULT_LEVELS = "0,20,40,60,80,100,120,140,160,180,200"
DEFAULT_PRODUCTS = "data/configs/unblinding_products.json"
DEFAULT_OUT = "results/unblinding"
DEFAULT_BASE_URL = "http://127.0.0.1:8080"
COVARIATE_KINDS = ("last_price", "competing_price", "expiry_days")

# After asking the manager to load a model, wait this long for it to be ready.
_HEALTH_WAIT_SECONDS = 300
_HEALTH_POLL_SECONDS = 5

# A chat function: message list and temperature in, raw model text out.
ChatFn = Callable[[list[dict[str, str]], float], str]


class UnreachableError(RuntimeError):
    """Raised when the chat server or the model manager cannot be reached."""


def main(argv: list[str] | None = None) -> int:
    """Run one full sweep; return the process exit code (0 means success).

    Parses the flags, checks the server is reachable (exit code 2 with a
    clear message when it is not), runs the demand sweep for every requested
    blinding condition, optionally runs the confounding diagnostic, saves all
    results under the --out directory, and writes a JSON run manifest.
    """
    args = _parse_args(argv)
    started = datetime.now(timezone.utc).isoformat()
    scope = _scope_for(args.blinding)
    draws = 1 if args.smoke else args.draws
    levels = _parse_levels(args.levels)
    if not levels:
        print(
            f"error: no price levels parsed from --levels {args.levels!r}",
            file=sys.stderr,
        )
        return 1
    covariates = _parse_covariates(args.covariates)
    products = _load_products(_resolve_products_path(args.products))
    if args.smoke:
        products = products[:1]
    if not products:
        print("error: the products file lists no products", file=sys.stderr)
        return 1
    design = _build_design(levels, scope, args.seed, covariates)
    safe_model = _safe_model_name(args.model)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    chat_fn = build_sweep_chat_fn(
        args.base_url, args.model, args.max_tokens, args.timeout
    )

    if args.manager_url:
        try:
            _switch_model(args.manager_url, args.model, args.manager_port, args.timeout)
            _wait_until_healthy(args.base_url, args.timeout)
        except UnreachableError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
    else:
        problem = _probe(_health_endpoint(args.base_url), args.timeout)
        if problem is not None:
            print(f"error: {problem}", file=sys.stderr)
            print(
                f"error: nothing listening at {args.base_url} - start the model "
                "server first or point --base-url at it",
                file=sys.stderr,
            )
            return 2

    multi = len(scope) > 1
    for blinding in scope:
        records = run_sweep(
            design,
            products,
            args.model,
            chat_fn,
            draws=draws,
            blinding=blinding,
            seed=args.seed,
        )
        base = out_dir / f"{safe_model}_{blinding}"
        _write_records(base, records)
        print(f"wrote {base}.jsonl and {base}.csv ({len(records)} records)")
        _print_demand_table(records, levels, blinding)
        if args.diagnose:
            diagnostic_file = (
                out_dir / f"{safe_model}_{blinding}_diagnostic.jsonl"
                if multi
                else out_dir / f"{safe_model}_diagnostic.jsonl"
            )
            _run_diagnostic(
                design,
                products,
                covariates,
                chat_fn,
                draws,
                blinding,
                args.seed,
                diagnostic_file,
            )
    finished = datetime.now(timezone.utc).isoformat()
    write_manifest(
        out_dir / "manifest.json",
        design,
        args.model,
        draws,
        scope,
        products,
        args.base_url,
        extra={
            "levels": levels,
            "temperature": args.temperature,
            "seed": args.seed,
            "argv": list(sys.argv),
            "started": started,
            "finished": finished,
        },
    )
    print(f"wrote {out_dir / 'manifest.json'}")
    return 0


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    """Read the command-line flags into one settings object."""
    parser = argparse.ArgumentParser(
        prog="unblinding_sweep",
        description=(
            "Run the price demand sweep and optional confounding diagnostic "
            "for the unblinding comparison against a local chat server."
        ),
    )
    parser.add_argument(
        "--model", required=True, help="model id sent to the chat server verbatim"
    )
    parser.add_argument(
        "--blinding",
        choices=("blinded", "unblinded", "both"),
        default="both",
        help="which blinding condition(s) to run (default: both)",
    )
    parser.add_argument(
        "--draws", type=int, default=5, help="chat draws per product and level"
    )
    parser.add_argument(
        "--products",
        default=DEFAULT_PRODUCTS,
        help="path to the products JSON file (default: %(default)s)",
    )
    parser.add_argument(
        "--levels",
        default=DEFAULT_LEVELS,
        help="comma list of price levels, percent of regular price",
    )
    parser.add_argument(
        "--out",
        default=DEFAULT_OUT,
        help="directory to write results into (default: %(default)s)",
    )
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help="chat server base url (default: %(default)s)",
    )
    parser.add_argument("--temperature", type=float, default=1.0)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--manager-url", default="", help="model manager base url")
    parser.add_argument("--manager-port", type=int, default=8080)
    parser.add_argument(
        "--diagnose",
        action="store_true",
        help="also run the covariate confounding diagnostic",
    )
    parser.add_argument(
        "--covariates",
        default=",".join(COVARIATE_KINDS),
        help="comma list of covariate kinds to probe",
    )
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="plumbing check: one product, one draw",
    )
    parser.add_argument("--max-tokens", type=int, default=16)
    parser.add_argument("--timeout", type=float, default=120.0)
    return parser.parse_args(argv)


def _scope_for(blinding: str) -> list[str]:
    """Turn the blinding choice into the list of blinding runs to do."""
    if blinding == "both":
        return ["blinded", "unblinded"]
    return [blinding]


def _safe_model_name(model: str) -> str:
    """Make a model id safe to use inside a file name."""
    return model.replace("/", "_").replace(" ", "_")


def _parse_levels(text: str) -> list[float]:
    """Read a comma-separated list of price percentages as floats."""
    return [float(piece.strip()) for piece in text.split(",") if piece.strip()]


def _parse_covariates(text: str) -> list[str]:
    """Read a comma-separated list of covariate kinds."""
    return [piece.strip() for piece in text.split(",") if piece.strip()]


def _load_products(path: Path) -> list[dict[str, Any]]:
    """Read the products file, accepting either a bare list or an object.

    The object shape carries the products under a "products" key; both shapes
    return a list of {"category", "product", "regular_price"} dicts.
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return data
    products = data.get("products")
    if not isinstance(products, list):
        raise ValueError(f"{path} has neither a bare product list nor a 'products' key")
    return products


def _resolve_products_path(value: str) -> Path:
    """Find the products file, also when relative to the repository root.

    A relative default such as data/configs/unblinding_products.json works
    when the script runs from anywhere inside the repository.
    """
    path = Path(value)
    if path.is_absolute() or path.exists():
        return path
    from_repo = _REPO_ROOT / value
    return from_repo if from_repo.exists() else path


def _build_design(
    levels: list[float],
    scope: list[str],
    seed: int | None,
    covariates: list[str],
) -> RandomizationDesign:
    """Build the price randomization design the sweep runs on."""
    blinding = scope[0] if len(scope) == 1 else "unblinded"
    return RandomizationDesign(
        variable="price",
        label="the price of the product",
        min_value=min(levels),
        max_value=max(levels),
        unit="% of regular price",
        distribution="grid",
        grid_points=len(levels),
        blinding=blinding,
        seed=seed,
        covariates_specified=list(covariates),
    )


def _server_root(base_url: str) -> str:
    """Normalize a server address: no trailing slash, no doubled /v1."""
    root = base_url.rstrip("/")
    if root.endswith("/v1"):
        root = root[: -len("/v1")]
    return root


def _health_endpoint(base_url: str) -> str:
    """Return the health-check url for a chat server base url."""
    return f"{_server_root(base_url)}/health"


def _post_json(url: str, payload: dict[str, Any], timeout: float) -> tuple[int, str]:
    """POST one JSON object and return the (status, body) pair."""
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url, data=body, method="POST", headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.status, response.read().decode("utf-8", errors="replace")


def _get(url: str, timeout: float) -> tuple[int, str]:
    """GET one url and return the (status, body) pair."""
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return response.status, response.read().decode("utf-8", errors="replace")


def build_sweep_chat_fn(
    base_url: str, model: str, max_tokens: int, timeout: float
) -> ChatFn:
    """Build the chat function the sweep kit calls during a run.

    The returned function posts one /v1/chat/completions request per call and
    retries once when the request fails or times out. On a final failure it
    logs the problem and returns "" so the sweep kit records the draw as
    failed instead of the whole run crashing.
    """

    def chat_fn(messages: list[dict[str, str]], temperature: float) -> str:
        url = f"{_server_root(base_url)}/v1/chat/completions"
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        last_error = ""
        for _attempt in range(2):
            try:
                status, body = _post_json(url, payload, timeout)
                data = json.loads(body)
                content = data["choices"][0]["message"].get("content")
                return content if isinstance(content, str) else ""
            except OSError as exc:
                last_error = str(exc)
            except (json.JSONDecodeError, KeyError, IndexError) as exc:
                last_error = f"unexpected reply: {exc}"
        print(
            f"warning: chat request to {url} failed ({last_error}); "
            "recording this draw as failed",
            file=sys.stderr,
        )
        return ""

    return chat_fn


def _probe(url: str, timeout: float) -> str | None:
    """Return None when a server answers, else a short error description.

    Any HTTP reply (even an error page) proves something is listening, so
    only connection-level problems count as unreachable here.
    """
    try:
        _get(url, timeout)
        return None
    except OSError as exc:
        return f"cannot reach {url}: {exc}"


def _switch_model(manager_url: str, model: str, port: int, timeout: float) -> None:
    """Ask the model manager to load one model on a port (expects HTTP 202)."""
    url = f"{manager_url.rstrip('/')}/switch"
    try:
        status, _body = _post_json(url, {"model": model, "port": port}, timeout)
    except OSError as exc:
        raise UnreachableError(f"cannot reach model manager {url}: {exc}") from exc
    if status != 202:
        raise UnreachableError(
            f"model manager {url} answered HTTP {status} instead of 202"
        )


def _wait_until_healthy(base_url: str, timeout: float) -> None:
    """Poll the chat server health endpoint until it reports healthy."""
    url = _health_endpoint(base_url)
    deadline = time.monotonic() + _HEALTH_WAIT_SECONDS
    while True:
        try:
            _status, body = _get(url, timeout)
            if _is_healthy_status(body):
                print(f"model healthy at {url}")
                return
        except OSError:
            pass
        if time.monotonic() >= deadline:
            raise UnreachableError(
                f"{url} did not report healthy within {_HEALTH_WAIT_SECONDS}s"
            )
        print(f"...waiting for {url} to report healthy", file=sys.stderr)
        time.sleep(_HEALTH_POLL_SECONDS)


def _is_healthy_status(body: str) -> bool:
    """Decide whether a health endpoint body means the server is healthy.

    Accepts {"status": true} (and string spellings such as "ok" or
    "healthy") as well as a plain "healthy" reply.
    """
    text = body.strip().lower()
    if "healthy" in text:
        return True
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError:
        return False
    if not isinstance(parsed, dict):
        return False
    status = parsed.get("status")
    if status is True:
        return True
    return isinstance(status, str) and status.lower() in ("ok", "healthy", "true")


def _write_records(base: Path, records: list[dict[str, Any]]) -> None:
    """Save sweep records to base.jsonl and base.csv.

    Every record becomes one JSON line in the .jsonl file and one row in the
    .csv file. CSV columns are the record keys that are not None everywhere;
    the header is written once when the file opens.
    """
    columns = [
        key
        for key in records[0]
        if any(record.get(key) is not None for record in records)
    ]
    with (
        Path(f"{base}.jsonl").open("w", encoding="utf-8") as jsonl_handle,
        Path(f"{base}.csv").open("w", newline="", encoding="utf-8") as csv_handle,
    ):
        writer = csv.DictWriter(csv_handle, fieldnames=columns)
        writer.writeheader()
        for record in records:
            jsonl_handle.write(json.dumps(record) + "\n")
            writer.writerow({key: _csv_cell(record[key]) for key in columns})


def _csv_cell(value: Any) -> Any:
    """Turn one record value into a CSV-safe cell; nested values become JSON."""
    if value is None:
        return ""
    if isinstance(value, (str, int, float, bool)):
        return value
    return json.dumps(value)


def _print_demand_table(
    records: list[dict[str, Any]], levels: list[float], blinding: str
) -> None:
    """Print the demand curve table for one blinding condition."""
    print(f"\nDemand curve ({blinding}):")
    print(f"{'level':>8} {'n':>4} {'p_buy':>7}")
    for bucket in aggregate_demand(records, levels):
        print(f"{bucket['level']:8g} {bucket['n']:4d} {bucket['p_buy']:7.3f}")


def _run_diagnostic(
    design: RandomizationDesign,
    products: list[dict[str, Any]],
    covariates: list[str],
    chat_fn: ChatFn,
    draws: int,
    blinding: str,
    seed: int | None,
    diagnostic_file: Path,
) -> None:
    """Run the confounding diagnostic, save its records, print the summary.

    Each chat call asks the model to fill in one covariate (past price,
    competing price, or expiry days) at a randomized price level. The saved
    records are flat {price: level, kind: filled} rows and the printed table
    reports Spearman rho with its confidence interval and an ok/mild/severe
    flag per covariate — confidence intervals only.
    """
    records = run_diagnostic(
        design,
        products,
        covariates,
        chat_fn,
        draws=draws,
        blinding=blinding,
        seed=seed,
    )
    with diagnostic_file.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record) + "\n")
    summary = summarize_confounding(records, design)
    print(
        f"\nConfounding diagnostic ({blinding}): {len(records)} records "
        f"-> {diagnostic_file}"
    )
    _print_diagnostic_table(summary)


def _print_diagnostic_table(
    summary: dict[str, dict[str, float | str]],
) -> None:
    """Print one confounding summary table (rho, CI, flag per covariate)."""
    print(f"{'covariate':<16} {'rho':>7} {'ci_lo':>7} {'ci_hi':>7}  flag")
    for kind, stats in sorted(summary.items()):
        print(
            f"{kind:<16} {stats['rho']:7.3f} {stats['ci_lo']:7.3f} "
            f"{stats['ci_hi']:7.3f}  {stats['flag']}"
        )


if __name__ == "__main__":
    raise SystemExit(main())
