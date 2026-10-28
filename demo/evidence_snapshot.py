"""Pin operator PNG bytes before FFmpeg consumes them (not LIVE attestation).

The bundle validates the pinned copy against the manifest *after* copying.
This closes the source-file verify/render time-of-check/time-of-use gap.
"""
from __future__ import annotations

import os
from pathlib import Path
import stat

MAX_CAPTURE_BYTES = 20 * 1024 * 1024


def _identity(info):
    return (info.st_dev, info.st_ino, info.st_size,
            info.st_mtime_ns, info.st_ctime_ns)


def pin_captures(source_root: Path, private_stage: Path, captures: list[dict]) -> Path:
    """Create owner-only regular-file snapshots; caller must verify snapshots.

    No symlinks, devices, FIFOs, path traversal or concurrent source mutation.
    The private stage is a new TemporaryDirectory controlled by the caller.
    """
    source_root, private_stage = Path(source_root), Path(private_stage)
    if source_root.is_symlink() or not source_root.is_dir():
        raise ValueError("evidence source must be a real directory")
    nofollow = getattr(os, "O_NOFOLLOW", None)
    if not isinstance(nofollow, int) or not nofollow:
        raise ValueError("O_NOFOLLOW required for capture snapshot")
    target_root = private_stage / "pinned-captures"
    target_root.mkdir(mode=0o700, exist_ok=False)
    names = set()
    for item in captures:
        name = item.get("file") if isinstance(item, dict) else None
        if (not isinstance(name, str) or not name.endswith(".png")
                or len(name) > 128 or Path(name).name != name
                or "\\" in name or name in names):
            raise ValueError("unsafe or duplicate capture filename")
        names.add(name)
        flags = os.O_RDONLY | nofollow | getattr(os, "O_NONBLOCK", 0)
        # Opening a descriptor rather than resolving a path prevents final
        # component symlink swaps after the initial manifest verification.
        with os.fdopen(os.open(source_root / name, flags), "rb") as src:
            before = os.fstat(src.fileno())
            if not stat.S_ISREG(before.st_mode) or not 32 <= before.st_size <= MAX_CAPTURE_BYTES:
                raise ValueError("capture must be a bounded regular file")
            copied = 0
            with (target_root / name).open("xb") as dst:
                os.fchmod(dst.fileno(), 0o600)
                while True:
                    block = src.read(min(1024 * 1024, MAX_CAPTURE_BYTES + 1 - copied))
                    if not block:
                        break
                    copied += len(block)
                    if copied > MAX_CAPTURE_BYTES:
                        raise ValueError("capture changed or exceeds size limit")
                    dst.write(block)
            after = os.fstat(src.fileno())
            if copied != before.st_size or _identity(before) != _identity(after):
                raise ValueError("capture changed during snapshot")
    return target_root
