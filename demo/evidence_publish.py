"""Fail-closed publication of a private five-capture evidence set.

Publication is not runtime attestation. The manifest is linked last, and any
failed link rolls back all files created by this invocation (never pre-existing
files). A host crash during publication still requires operator cleanup.
"""
from __future__ import annotations

import os
from pathlib import Path
import re

_SAFE_SERVICE = re.compile(r"^[a-z][a-z0-9_-]{0,31}$")


def publish_capture_set(staging: Path, destination: Path, services: tuple[str, ...]) -> None:
    staging, destination = Path(staging), Path(destination)
    if not services or len(services) != len(set(services)) or any(
        not isinstance(service, str) or not _SAFE_SERVICE.fullmatch(service)
        for service in services
    ):
        raise ValueError("invalid capture service names")
    names = tuple(service + ".png" for service in services) + ("manifest.json",)
    if staging.is_symlink() or not staging.is_dir() or destination.is_symlink() or not destination.is_dir():
        raise ValueError("regular staging and destination directories required")
    for name in names:
        source, target = staging / name, destination / name
        if source.is_symlink() or not source.is_file():
            raise ValueError("missing or symlinked staged capture")
        if target.exists() or target.is_symlink():
            raise ValueError("refusing to overwrite existing evidence")
    created = []
    try:
        for name in names:
            target = destination / name
            os.link(staging / name, target)
            created.append(target)
    except OSError:
        for target in reversed(created):
            target.unlink()
        raise
