# This file owns the production model server: it starts ONE direct
# llama-server at a time on port 8080 (the port that is record-compatible
# with the frozen runs; LM Studio's app server on 1234 is not), using the
# frozen expansion pipeline's serve table (the same GGUF files, the same
# launch flags, the same chat-template overrides). The process is started
# in its own session (setsid-style) so it survives the runner, and its
# PID goes in the pidfile the stop tooling reads. Functions:
#   load_pipeline  — the frozen expansion pipeline (read-only import).
#   start_model    — stop any previous server, launch this model's GGUF,
#                    wait for health, verify identity, send the canary.
#   stop_server    — stop the current llama-server via the pidfile.
from __future__ import annotations

import subprocess
import time
import urllib.request

from twin2k10r.integration.production.model_ids import server_model_id


class ServingError(RuntimeError):
    """A model could not be served, verified, or reached."""


def load_pipeline():
    """The frozen expansion pipeline package (its serving config lives
    there; this module never edits it)."""
    from twin2k10r.integration.production.driver_expansion import (
        load_pipeline as _load,
    )

    return _load()


def start_model(model: str, base_url: str, log) -> dict:
    """Serve one production model on base_url and prove it answers.

    Reuses the frozen serve table (GGUF path + chat template) and launch
    flags verbatim; the only difference from the historical launcher is
    that the process starts in its OWN session (setsid semantics) so a
    runner crash never takes the server down mid-model, and the PID file
    is written atomically. Returns the canary stamp.
    """
    pipeline = load_pipeline()
    config = pipeline.config
    if model not in config.SERVE_TABLE:
        raise ServingError(f"no serve entry for {model!r}")
    gguf_path, template_args = config.SERVE_TABLE[model]
    if not gguf_path.exists():
        raise ServingError(f"weights missing: {gguf_path}")
    if not config.LLAMA_SERVER_BIN.exists():
        raise ServingError(
            f"llama-server binary missing: {config.LLAMA_SERVER_BIN}")
    pipeline.serving._stop_previous_server()
    _launch(config, gguf_path, template_args, base_url, log)
    pipeline.serving.verify_identity(str(gguf_path), base_url)
    stamp = pipeline.serving.canary(server_model_id(model), base_url)
    log(f"canary for {model}: {stamp}")
    return stamp


def _launch(config, gguf_path, template_args, base_url, log) -> None:
    """One llama-server launch, own session, atomic pidfile, health wait."""
    import urllib.parse

    port = urllib.parse.urlparse(base_url).port or 8080
    command = [
        str(config.LLAMA_SERVER_BIN),
        "--model", str(gguf_path),
        "--port", str(port),
        *config.LLAMA_SERVER_FLAGS,
        *template_args,
    ]
    log_handle = open("/tmp/t2kx-llama-server.out", "ab")
    # start_new_session=True: the server becomes its own process group
    # (setsid semantics) and survives the runner being killed.
    process = subprocess.Popen(
        command, stdout=log_handle, stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    from twin2k10r.integration.production import safeguards

    safeguards.write_atomic_json(
        config.LLAMA_SERVER_PID_FILE, {"pid": process.pid})
    log(f"launched llama-server pid {process.pid} for {gguf_path.name}")
    _wait_healthy(base_url, gguf_path, process)


def _wait_healthy(base_url: str, gguf_path, process) -> None:
    """Poll /health until the server answers; raise on early exit."""
    deadline = time.monotonic() + 600  # big models page off disk slowly
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise ServingError(
                f"llama-server exited early (code {process.returncode}) "
                f"for {gguf_path.name} — see /tmp/t2kx-llama-server.out")
        try:
            with urllib.request.urlopen(f"{base_url.rstrip('/')}/health",
                                        timeout=5) as response:
                if response.status == 200:
                    return
        except (urllib.error.URLError, OSError):
            pass
        time.sleep(3)
    raise ServingError(
        f"llama-server for {gguf_path.name} not healthy within 600s")


def stop_server() -> None:
    """Stop the current llama-server via the frozen pidfile convention."""
    load_pipeline().serving._stop_previous_server()
