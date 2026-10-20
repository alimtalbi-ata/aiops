#!/usr/bin/env python3
"""Copy the audited source tree for packaging without relying on .git.

The cumulative ZIP must be rebuildable from an extracted source kit. Explicit
allowlists prevent .env, backup dumps, generated logs, caches and credentials
from accidentally entering a distributable.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import sys

SOURCE_DIRECTORIES = (
    "00-Deployment", ".github", "app", "config", "db", "deploy",
    "docs", "eval", "integration", "manifests", "schemas", "tests", "tools",
)
SOURCE_FILES = (
    ".dockerignore", ".gitignore", "LICENSE", "README.md", "VERSION",
    "compose.yml", "pyproject.toml",
)
EXCLUDED_NAMES = {
    ".env", ".env.local", ".env.production", "__pycache__", ".pytest_cache",
    ".mypy_cache", ".venv", "venv", ".git", "node_modules", "dist", "backups",
    "reports", "secrets", ".DS_Store",
}
EXCLUDED_SUFFIXES = (
    ".pyc", ".pyo", ".pem", ".p12", ".pfx", ".key", ".jks",
    ".sqlite", ".db", ".dump", ".tar.gz", ".sql.gz",
)
REQUIRED_FILES = ("compose.yml", "VERSION", "deploy/install-isolated.sh",
                  "deploy/migrate.sh", "app/worker/workflow.py")


class PackagingError(ValueError):
    pass


def eligible(path: Path) -> bool:
    if path.is_symlink():
        return False
    if path.name in EXCLUDED_NAMES or path.name.startswith(".env."):
        return path.name == ".env.example"
    return not path.name.lower().endswith(EXCLUDED_SUFFIXES)


def prepare_copy(source: Path, destination: Path) -> int:
    source = source.resolve()
    destination = destination.resolve()
    if source == destination or source in destination.parents is False and destination in source.parents:
        raise PackagingError("unsafe_source_destination_overlap")
    if destination.exists() and any(destination.iterdir()):
        raise PackagingError("destination_not_empty")
    for relative in REQUIRED_FILES:
        item = source / relative
        if not item.is_file() or item.is_symlink():
            raise PackagingError("required_source_missing:" + relative)
    destination.mkdir(parents=True, exist_ok=True)
    files_copied = 0
    for relative in SOURCE_FILES:
        src = source / relative
        if src.is_file() and eligible(src):
            shutil.copy2(src, destination / relative)
            files_copied += 1
    for directory_name in SOURCE_DIRECTORIES:
        root = source / directory_name
        if not root.is_dir() or root.is_symlink():
            continue
        for src in sorted(root.rglob("*")):
            relative = src.relative_to(source)
            if any(not eligible(source / Path(*relative.parts[:index]))
                   for index in range(1, len(relative.parts) + 1)):
                continue
            dst = destination / relative
            if src.is_dir():
                dst.mkdir(parents=True, exist_ok=True)
            elif src.is_file():
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
                files_copied += 1
    if files_copied < len(REQUIRED_FILES):
        raise PackagingError("source_copy_incomplete")
    return files_copied


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        count = prepare_copy(args.source, args.destination)
    except (OSError, PackagingError) as exc:
        print("OFFLINE_PACKAGE_COPY=FAIL|" + str(exc), file=sys.stderr)
        return 1
    print("OFFLINE_PACKAGE_COPY=PASS|files=" + str(count))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
