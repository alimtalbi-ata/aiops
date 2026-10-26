#!/usr/bin/env python3
"""Run Docker Compose with a narrowly-scoped retry for transient BuildKit transport loss."""
from __future__ import annotations

import subprocess
import sys
import time
from collections.abc import Callable, Sequence
from typing import TextIO

MAX_ATTEMPTS = 2
RETRY_DELAY_SECONDS = 2
_TRANSIENT_MARKERS = (
    "failed to receive status: rpc error: code = unavailable desc = error reading from server: eof",
    "rpc error: code = unavailable desc = transport is closing",
    "failed to solve: unexpected eof",
)


def is_transient_transport_failure(output: str) -> bool:
    """Return true only for reviewed BuildKit/daemon transport-loss signatures."""
    normalized = output.casefold()
    return any(marker in normalized for marker in _TRANSIENT_MARKERS)


def run_compose(
    args: Sequence[str],
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
    sleeper: Callable[[float], None] | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    """Execute Docker Compose; preserve all final and unrecognized failures."""
    out = stdout if stdout is not None else sys.stdout
    err = stderr if stderr is not None else sys.stderr
    if not args:
        print("usage: ci_docker_build.py [docker compose arguments ...]", file=err)
        return 2

    execute = runner if runner is not None else subprocess.run
    wait = sleeper if sleeper is not None else time.sleep
    command = ["docker", "compose", *args]

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            result = execute(command, capture_output=True, text=True, check=False)
        except OSError:
            print("[ci-docker-build] docker_compose_launch_failed", file=err)
            return 127

        if result.stdout:
            out.write(result.stdout)
        if result.stderr:
            err.write(result.stderr)
        if result.returncode == 0:
            return 0

        combined_output = f"{result.stdout or ''}\n{result.stderr or ''}"
        if attempt >= MAX_ATTEMPTS or not is_transient_transport_failure(combined_output):
            return result.returncode or 1

        print(
            "[ci-docker-build] recognized transient BuildKit/daemon transport failure; "
            f"retrying once after {RETRY_DELAY_SECONDS}s (attempt {attempt}/{MAX_ATTEMPTS})",
            file=err,
        )
        wait(RETRY_DELAY_SECONDS)

    return 1


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args in ([], ["--help"], ["-h"]):
        print("usage: python tools/ci_docker_build.py [docker compose arguments ...]")
        return 0 if args else 2
    if args and args[0] == "--":
        args.pop(0)
    return run_compose(args)


if __name__ == "__main__":
    raise SystemExit(main())
