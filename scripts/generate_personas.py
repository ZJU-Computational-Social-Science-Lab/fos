"""Generate step-A personas for a product category through a local chat server.

This script draws personas for one product: it asks an LLM chat server to
fill the eleven-field persona template once per draw (Gui & Toubia Web
Appendix D step A), parses each answer, and writes the accepted personas as
JSON Lines plus a summary JSON with diversity, coherence, and census-gap
reports. All of the persona logic lives in fos.experiments.personas; this
script only talks to the network, saves the results, and prints a short
summary. Importing the module never opens a socket.

What each function does:
    main(argv)            - The entry point: parse flags, draw personas, save
                            the JSONL and summary files, print the report.
    _parse_args(argv)     - Turn command-line flags into a settings object.
    _build_chat_fn(...)   - Build the chat function the personas module
                            calls; one retry, "" on final failure.
    _post_json(url, ...)  - POST one JSON object and return (status, body).
    _server_root(base)    - Normalize a server address for joining.
    _write_personas(...)  - Save accepted personas as one JSON line each.
    _build_summary(...)   - Combine the diversity, coherence and census
                            reports into the summary payload.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

# Make this worktree's `src` importable when the script runs directly.
_REPO_ROOT = Path(__file__).resolve().parent.parent
_SRC_DIR = _REPO_ROOT / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from fos.experiments.personas import (  # noqa: E402
    check_persona_coherence,
    check_persona_diversity,
    compare_to_census,
    generate_personas,
    load_census_marginals,
)

# Command-line defaults (see the task spec).
DEFAULT_N = 500
DEFAULT_OUT = "results/personas"
DEFAULT_BASE_URL = "http://127.0.0.1:8080"
DEFAULT_TEMPERATURE = 1.0

# How long a single chat request may take before it is retried.
_CHAT_TIMEOUT = 120.0

# A chat function: message list and temperature in, raw model text out.
ChatFn = Callable[[list[dict[str, str]], float], str]


def main(argv: list[str] | None = None) -> int:
    """Run one persona generation; return the process exit code.

    Parses the flags, requires a model id, draws args.n personas through the
    chat server, writes the accepted personas to one JSONL file and the
    diversity / coherence / census-gap reports to a summary JSON, both under
    the --out directory, then prints a one-line summary.
    """
    args = _parse_args(argv)
    if not args.model:
        print("error: --model is required", file=sys.stderr)
        return 2
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    started = datetime.now(timezone.utc).isoformat()
    chat_fn = _build_chat_fn(args.base_url, args.model)
    personas, skipped = generate_personas(
        args.category,
        args.product,
        args.n,
        chat_fn,
        temperature=args.temperature,
        seed=args.seed,
    )
    personas_file = _write_personas(out_dir, personas)
    summary_file = _write_summary(
        out_dir / "summary.json",
        _build_summary(args, personas, skipped, started),
    )
    print(f"generated {len(personas)} personas ({skipped} skipped) -> {personas_file}")
    print(f"wrote {summary_file}")
    return 0


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    """Read the command-line flags into one settings object."""
    parser = argparse.ArgumentParser(
        prog="generate_personas",
        description=(
            "Draw step-A personas for one product through a local chat "
            "server and write persona JSONL plus a summary report."
        ),
    )
    parser.add_argument(
        "--category", required=True, help="product category, e.g. Soft Drinks"
    )
    parser.add_argument(
        "--product", required=True, help="product name shown to the model"
    )
    parser.add_argument(
        "--n",
        type=int,
        default=DEFAULT_N,
        help="personas to draw (default: %(default)s)",
    )
    parser.add_argument(
        "--out",
        default=DEFAULT_OUT,
        help="directory to write results into (default: %(default)s)",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="model id sent to the chat server verbatim",
    )
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help="chat server base url (default: %(default)s)",
    )
    parser.add_argument("--temperature", type=float, default=DEFAULT_TEMPERATURE)
    parser.add_argument("--seed", type=int, default=None)
    return parser.parse_args(argv)


def _server_root(base_url: str) -> str:
    """Normalize a server address: no trailing slash, no doubled /v1."""
    root = base_url.rstrip("/")
    if root.endswith("/v1"):
        root = root[: -len("/v1")]
    return root


def _post_json(url: str, payload: dict[str, Any], timeout: float) -> tuple[int, str]:
    """POST one JSON object and return the (status, body) pair."""
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url, data=body, method="POST", headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.status, response.read().decode("utf-8", errors="replace")


def _build_chat_fn(base_url: str, model: str) -> ChatFn:
    """Build the chat function the personas module calls during a run.

    The returned function posts one /v1/chat/completions request per call
    and retries once when the request fails or times out. On a final failure
    it logs the problem and returns "" so the draw is counted as skipped
    instead of the whole run crashing.
    """

    def chat_fn(messages: list[dict[str, str]], temperature: float) -> str:
        url = f"{_server_root(base_url)}/v1/chat/completions"
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        last_error = ""
        for _attempt in range(2):
            try:
                _status, body = _post_json(url, payload, _CHAT_TIMEOUT)
                data = json.loads(body)
                content = data["choices"][0]["message"].get("content")
                return content if isinstance(content, str) else ""
            except OSError as exc:
                last_error = str(exc)
            except (json.JSONDecodeError, KeyError, IndexError) as exc:
                last_error = f"unexpected reply: {exc}"
        print(
            f"warning: chat request to {url} failed ({last_error}); "
            "recording this draw as skipped",
            file=sys.stderr,
        )
        return ""

    return chat_fn


def _write_personas(out_dir: Path, personas: list[dict[str, Any]]) -> Path:
    """Save each accepted persona as one JSON line; return the file path."""
    target = out_dir / "personas.jsonl"
    with target.open("w", encoding="utf-8") as handle:
        for persona in personas:
            handle.write(json.dumps(persona) + "\n")
    return target


def _build_summary(
    args: argparse.Namespace,
    personas: list[dict[str, Any]],
    skipped: int,
    started: str,
) -> dict[str, Any]:
    """Combine the diversity, coherence and census reports into one payload."""
    diversity = check_persona_diversity(personas)
    coherence = check_persona_coherence(personas)
    census_gap = compare_to_census(personas, load_census_marginals())
    return {
        "category": args.category,
        "product": args.product,
        "model": args.model,
        "n_requested": args.n,
        "n_personas": len(personas),
        "n_skipped": skipped,
        "temperature": args.temperature,
        "seed": args.seed,
        "started": started,
        "finished": datetime.now(timezone.utc).isoformat(),
        "diversity": diversity,
        "coherence": coherence,
        "census_gap": census_gap,
    }


def _write_summary(path: Path, summary: dict[str, Any]) -> Path:
    """Save the summary payload as pretty JSON; return the file path."""
    path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return path


if __name__ == "__main__":
    raise SystemExit(main())
