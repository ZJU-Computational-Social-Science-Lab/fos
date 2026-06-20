"""
Regression test for llama.cpp router --models-preset cascade.

Checks that --chat-template-file and --reasoning off settings from the
[*] section of models.ini are passed to child processes spawned by the router.
This test runs against a real router on localhost:8080 and does NOT import
any FOS modules — it is a standalone integration test.

Test steps:
    1. Confirm the router is reachable on localhost:8080
    2. Load model A via POST /models/load
    3. Parse the child process command line — confirm --chat-template-file and --reasoning are present
    4. Unload model A
    5. Load model B
    6. Confirm --chat-template-file and --reasoning are STILL present on the child
    7. Print PASS/FAIL for each check
"""

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROUTER_URL = "http://127.0.0.1:8080"
HEALTH_URL = f"{ROUTER_URL}/health"
MODELS_URL = f"{ROUTER_URL}/models"
LOAD_URL = f"{ROUTER_URL}/models/load"
UNLOAD_URL = f"{ROUTER_URL}/models/unload"

# Use a lightweight model for speed
MODEL_A = "gpt-oss-20b"
MODEL_B = "gemma-4-26b-a4b"

EXPECTED_FLAGS = ["chat-template-file", "reasoning"]

# ── helpers ──────────────────────────────────────────────────────────


def http_get(url: str, timeout: int = 10) -> dict | None:
    """Send a GET request and return parsed JSON, or None on failure."""
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, json.JSONDecodeError) as exc:
        print(f"  [WARN] GET {url} failed: {exc}")
        return None


def http_post(url: str, body: dict, timeout: int = 30) -> dict | None:
    """Send a POST request with JSON body and return parsed JSON."""
    data = json.dumps(body).encode("utf-8")
    try:
        req = urllib.request.Request(url, data=data, method="POST")
        req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, json.JSONDecodeError) as exc:
        print(f"  [WARN] POST {url} failed: {exc}")
        return None


def find_child_pid() -> int | None:
    """Return the PID of the first llama-server child process (no --models-dir)."""
    try:
        result = subprocess.run(
            ["ps", "aux"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        for line in result.stdout.splitlines():
            if "llama-server" in line and "--models-dir" not in line:
                parts = line.split()
                if parts:
                    return int(parts[1])
    except (subprocess.TimeoutExpired, ValueError, IndexError):
        pass
    return None


def get_child_cmdline(pid: int) -> str | None:
    """Read /proc/PID/cmdline and return as a space-joined string."""
    try:
        with open(f"/proc/{pid}/cmdline", "r", encoding="utf-8") as f:
            raw = f.read()
        return raw.replace("\0", " ").strip()
    except (FileNotFoundError, PermissionError, OSError):
        return None


def child_has_flag(pid: int, flag: str) -> bool:
    """Check whether the child process cmdline contains the given flag."""
    cmdline = get_child_cmdline(pid)
    if cmdline is None:
        return False
    return f"--{flag}" in cmdline


def load_model(model_name: str) -> bool:
    """Load a model on the router. Returns True if accepted."""
    resp = http_post(LOAD_URL, {"model": model_name})
    if resp and resp.get("success"):
        print(f"  Model '{model_name}' load accepted")
        return True
    print(f"  FAIL: model '{model_name}' load was not accepted: {resp}")
    return False


def unload_model(model_name: str) -> bool:
    """Unload a model on the router. Returns True if accepted."""
    resp = http_post(UNLOAD_URL, {"model": model_name})
    if resp and resp.get("success"):
        print(f"  Model '{model_name}' unloaded")
        return True
    print(f"  WARN: model '{model_name}' unload was not accepted: {resp}")
    return False


def wait_for_child(timeout: int = 60) -> int | None:
    """Poll until a child llama-server process appears (no --models-dir)."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        pid = find_child_pid()
        if pid is not None:
            return pid
        time.sleep(2)
    return None


def wait_for_child_dead(timeout: int = 30) -> bool:
    """Poll until the child process disappears."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if find_child_pid() is None:
            return True
        time.sleep(1)
    return False


# ── main ─────────────────────────────────────────────────────────────


def main() -> int:
    """Run the regression test. Returns 0 on PASS, 1 on FAIL."""
    passed = 0
    failed = 0

    print("=" * 60)
    print("Template Propagation Regression Test")
    print("=" * 60)
    print()

    # ── 1. Router health check ─────────────────────────────────────
    print("[1/6] Checking router health...")
    health = http_get(HEALTH_URL)
    if health is not None:
        print("  PASS: Router is reachable on port 8080")
        passed += 1
    else:
        print("  FAIL: Router is NOT reachable on port 8080")
        failed += 1
        print("\nAborting — router must be running.")
        return 1

    # ── 2. Load model A ───────────────────────────────────────────
    print(f"\n[2/6] Loading model A ({MODEL_A})...")
    if not load_model(MODEL_A):
        print("  FAIL: Could not load model A")
        failed += 1
        return 1

    # ── 3. Verify flags on child A ─────────────────────────────────
    print(f"\n[3/6] Verifying flags on child process for {MODEL_A}...")
    pid_a = wait_for_child()
    if pid_a is None:
        print("  FAIL: No child process appeared for model A")
        failed += 1
    else:
        cmdline = get_child_cmdline(pid_a)
        print(f"  Child PID: {pid_a}")
        print(f"  Cmdline: {cmdline}")
        all_ok = True
        for flag in EXPECTED_FLAGS:
            if child_has_flag(pid_a, flag):
                print(f"  PASS: --{flag} is present")
                passed += 1
            else:
                print(f"  FAIL: --{flag} is MISSING")
                failed += 1
                all_ok = False

    # ── 4. Unload A, load B ────────────────────────────────────────
    print(f"\n[4/6] Switching to model B ({MODEL_B})...")
    if not unload_model(MODEL_A):
        print("  WARN: Unload A may not have succeeded; continuing...")
    time.sleep(2)

    if not load_model(MODEL_B):
        print("  FAIL: Could not load model B")
        failed += 1
        return 1

    # ── 5. Verify flags on child B ─────────────────────────────────
    print(f"\n[5/6] Verifying flags on child process for {MODEL_B}...")
    time.sleep(2)
    pid_b = wait_for_child()
    if pid_b is None:
        print("  FAIL: No child process appeared for model B")
        failed += 1
    else:
        cmdline = get_child_cmdline(pid_b)
        print(f"  Child PID: {pid_b}")
        print(f"  Cmdline: {cmdline}")
        for flag in EXPECTED_FLAGS:
            if child_has_flag(pid_b, flag):
                print(f"  PASS: --{flag} is still present after model switch")
                passed += 1
            else:
                print(f"  FAIL: --{flag} is MISSING after model switch")
                failed += 1

    # ── 6. Cleanup ─────────────────────────────────────────────────
    print(f"\n[6/6] Cleaning up...")
    unload_model(MODEL_B)

    # ── Summary ────────────────────────────────────────────────────
    print()
    print("=" * 60)
    print(f"Result: {passed} passed, {failed} failed")
    print("=" * 60)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
