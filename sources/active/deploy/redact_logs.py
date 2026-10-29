#!/usr/bin/env python3
"""Fail-closed redaction of operational logs using exact secret values from .env.

This process never writes or prints .env content; it emits sanitized stdin.
Review diagnostic bundles before exporting them.
"""
from __future__ import annotations
import re
import sys
from pathlib import Path

SENSITIVE_NAME = re.compile(r"(PASSWORD|PASSWD|SECRET|TOKEN|API[_-]?KEY|CREDENTIAL|ENCRYPTION[_-]?KEY|AUTHORIZATION|PRIVATE[_-]?KEY)", re.I)
ASSIGNMENT = re.compile(r"(?i)\b([A-Z0-9_]*(?:PASSWORD|PASSWD|SECRET|TOKEN|API[_-]?KEY|ENCRYPTION[_-]?KEY|CREDENTIAL|AUTHORIZATION|PRIVATE[_-]?KEY)[A-Z0-9_]*)\s*([=:])\s*([^\s,;]+)")
BEARER = re.compile(r"(?i)(\bBearer\s+)[^\s,;]+")
PG_URI = re.compile(r"(?i)(\bpostgres(?:ql)?://[^:/\s]+:)[^@\s]+(@)")
COMMON_URL = re.compile(r"(?i)(\b(?:https?|mysql|mariadb)://[^:/\s]+:)[^@\s]+(@)")
PASSWORD_OPT = re.compile(r"(?i)(--(?:password|token|api-key)\s*(?:=|\s)\s*)[^\s,;]+")


def load_secret_values(env_file: Path) -> list[str]:
    secrets = set()
    if not env_file.is_file():
        return []
    for line in env_file.read_text(encoding="utf-8", errors="replace").splitlines():
        if "=" not in line or line.lstrip().startswith("#"):
            continue
        name, value = line.split("=", 1)
        if not SENSITIVE_NAME.search(name):
            continue
        value = value.strip().strip("\"'")
        if len(value) >= 8:
            secrets.add(value)
    return sorted(secrets, key=len, reverse=True)


def scrub(line: str, secrets: list[str]) -> str:
    for secret in secrets:
        line = line.replace(secret, "[REDACTED]")
    line = PG_URI.sub(r"\1[REDACTED]\2", line)
    line = COMMON_URL.sub(r"\1[REDACTED]\2", line)
    line = BEARER.sub(r"\1[REDACTED]", line)
    line = PASSWORD_OPT.sub(r"\1[REDACTED]", line)
    line = ASSIGNMENT.sub(r"\1\2[REDACTED]", line)
    return line


def main() -> int:
    if len(sys.argv) != 2:
        print("USAGE: redact_logs.py <private-.env-path>", file=sys.stderr)
        return 2
    env = Path(sys.argv[1])
    if not env.is_file():
        print("FAIL|private_env_unavailable_for_redaction", file=sys.stderr)
        return 3
    secrets = load_secret_values(env)
    for line in sys.stdin:
        sys.stdout.write(scrub(line, secrets))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
