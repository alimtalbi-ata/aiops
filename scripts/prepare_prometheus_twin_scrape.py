#!/usr/bin/env python3
"""Explicit operator preflight for a dedicated Twin Prometheus scrape credential.

No network calls. No secrets printed. Never invoked by the Debian poller.
The private host directory (0700) protects a file readable by Prometheus's
non-root UID after Docker bind-mounts the individual file into its container.
"""
from __future__ import annotations
import argparse
import os
from pathlib import Path
import re
import secrets
import stat
import sys
import tempfile

KEY = "AIOPS_TWIN_METRICS_TOKEN"
TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_-]{16,256}\Z")

class Blocked(ValueError):
    pass

def _read_env(path: Path) -> tuple[str, dict[str, str]]:
    if path.is_symlink() or not path.is_file() or path.stat().st_mode & 0o077:
        raise Blocked("unsafe_env_file")
    raw = path.read_text(encoding="utf-8")
    values = {}
    for line in raw.splitlines():
        if not line or line.lstrip().startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key in values:
            raise Blocked("duplicate_env_key")
        values[key] = value
    return raw, values

def _atomic(path: Path, content: str, mode: int) -> None:
    fd, tmp = tempfile.mkstemp(prefix=".scrape-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)

def prepare(env_file: Path, output: Path, *, provision: bool = False, check: bool = False) -> None:
    raw, values = _read_env(env_file)
    token = values.get(KEY, "")
    if not token and provision and not check:
        token = secrets.token_hex(32)
        if KEY in values:
            lines = raw.splitlines(keepends=True)
            raw = "".join(KEY + "=" + token + ("\n" if line.endswith("\n") else "")
                          if line.startswith(KEY + "=") else line for line in lines)
        else:
            raw = raw.rstrip("\n") + "\n" + KEY + "=" + token + "\n"
        _atomic(env_file, raw, 0o600)
        _, values = _read_env(env_file)
    if not TOKEN_PATTERN.fullmatch(token):
        raise Blocked("missing_or_invalid_metrics_token")
    if token in (values.get("AIOPS_ADMIN_TOKEN"), values.get("AIOPS_INTERNAL_TOKEN")):
        raise Blocked("metrics_token_not_distinct")
    if output.is_symlink() or (output.exists() and not output.is_file()):
        raise Blocked("unsafe_output")
    if check:
        if not output.is_file() or output.read_text(encoding="utf-8") != token:
            raise Blocked("missing_or_stale_scrape_file")
        if output.stat().st_mode & 0o777 != 0o644:
            raise Blocked("scrape_file_mode")
        return
    # The bind-mounted file must be readable by Prometheus's non-root UID.
    # Its host parent is private (0700), and the directory is never mounted.
    for directory in (output.parent.parent, output.parent):
        if directory.is_symlink() or (directory.exists() and not directory.is_dir()):
            raise Blocked("unsafe_output_directory")
        directory.mkdir(mode=0o700, exist_ok=True)
        directory.chmod(0o700)
    _atomic(output, token, 0o644)

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--output", type=Path, default=Path(".local/prometheus/twin-metrics-token"))
    parser.add_argument("--provision", action="store_true",
                        help="explicitly generate missing dedicated token in existing .env")
    parser.add_argument("--check", action="store_true",
                        help="verify file matches .env without writing")
    args = parser.parse_args()
    try:
        if args.check and args.provision:
            raise Blocked("incompatible_options")
        prepare(args.env_file, args.output, provision=args.provision, check=args.check)
    except (Blocked, OSError, UnicodeError) as exc:
        code = str(exc) if isinstance(exc, Blocked) else "filesystem_error"
        print("SCRAPE_CREDENTIAL=BLOCKED reason=" + code)
        return 2
    print("SCRAPE_CREDENTIAL=READY (secret not printed)")
    return 0

if __name__ == "__main__":
    sys.exit(main())
