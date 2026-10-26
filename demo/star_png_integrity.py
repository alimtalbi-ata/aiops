"""Bounded structural PNG verification for offline STAR screenshot evidence.

CRC and chunk checks are NOT browser/runtime authentication or pixel decoding.
No network, decompression, execution or application mutation.
"""
from __future__ import annotations
import hashlib
import os
import stat
import struct
import zlib
from pathlib import Path

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
MAX_BYTES = 15_000_000
MAX_DIMENSION = 16_384
MAX_PIXELS = 16_777_216
_VALID_DEPTHS = {0: {1, 2, 4, 8, 16}, 2: {8, 16}, 3: {1, 2, 4, 8}, 4: {8, 16}, 6: {8, 16}}
_KNOWN_CRITICAL = {b"IHDR", b"PLTE", b"IDAT", b"IEND"}
_TEXT_CHUNKS = {b"tEXt", b"zTXt", b"iTXt"}

def inspect_png(path: Path, max_bytes: int = MAX_BYTES) -> tuple[str, int]:
    """Return (SHA-256, bytes) for a structurally checked PNG, never proof of origin."""
    if not 33 <= max_bytes <= MAX_BYTES:
        raise ValueError("invalid PNG size limit")
    # Refuse symlinks early and pin every check to one open descriptor.
    # O_NOFOLLOW closes the check/open race where the platform supports it;
    # O_NONBLOCK prevents a substituted FIFO from hanging the offline verifier.
    if path.is_symlink():
        raise ValueError("capture symlink is forbidden")
    flags = (os.O_RDONLY | getattr(os, "O_BINARY", 0)
             | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
    try:
        fd = os.open(path, flags)
    except OSError as exc:
        raise ValueError("capture file cannot be opened safely") from exc

    try:
        # Check the descriptor before wrapping it: fdopen may reject a
        # directory itself, which must become a controlled validation error.
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode):
            raise ValueError("capture must be a regular file")
        size = before.st_size
        if size < 57 or size > max_bytes:
            raise ValueError("capture size outside limits")
        digest = hashlib.sha256()
        stream = os.fdopen(fd, "rb")
        fd = None  # stream now owns the descriptor
    except Exception:
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass
        raise

    with stream:
        def read_exact(count: int) -> bytes:
            data = stream.read(count)
            if len(data) != count:
                raise ValueError("truncated PNG")
            digest.update(data)
            return data

        if read_exact(8) != PNG_SIGNATURE:
            raise ValueError("invalid PNG signature")
        offset = 8
        seen_ihdr = False
        seen_idat = False
        idat_ended = False
        seen_plte = False
        seen_iend = False
        while offset < size:
            if size - offset < 12:
                raise ValueError("truncated PNG chunk")
            length = struct.unpack(">I", read_exact(4))[0]
            kind = read_exact(4)
            offset += 8
            if length > size - offset - 4 or length > max_bytes:
                raise ValueError("invalid PNG chunk length")
            if (len(kind) != 4 or any(not (65 <= x <= 90 or 97 <= x <= 122) for x in kind)
                    or 97 <= kind[2] <= 122):
                raise ValueError("invalid PNG chunk type")
            if kind in _TEXT_CHUNKS:
                raise ValueError("PNG embedded text metadata is prohibited")
            if kind[0] & 32 == 0 and kind not in _KNOWN_CRITICAL:
                raise ValueError("unknown critical PNG chunk")
            if not seen_ihdr and (kind != b"IHDR" or length != 13):
                raise ValueError("PNG must begin with 13-byte IHDR")
            if seen_iend:
                raise ValueError("PNG data after IEND")
            if kind == b"IHDR" and seen_ihdr:
                raise ValueError("duplicate PNG IHDR")
            if kind == b"PLTE" and (seen_plte or seen_idat or length == 0 or length % 3 or length > 768):
                raise ValueError("invalid PNG palette")
            if kind == b"IDAT" and (idat_ended or length == 0):
                raise ValueError("invalid PNG IDAT sequence")
            if kind == b"IEND" and (not seen_idat or length != 0):
                raise ValueError("invalid PNG IEND")
            crc = zlib.crc32(kind)
            remaining = length
            ihdr = b""
            while remaining:
                block = read_exact(min(remaining, 65536))
                if kind == b"IHDR":
                    ihdr += block
                crc = zlib.crc32(block, crc)
                remaining -= len(block)
            declared_crc = struct.unpack(">I", read_exact(4))[0]
            offset += length + 4
            if declared_crc != crc:
                raise ValueError("PNG chunk CRC mismatch")
            if kind == b"IHDR":
                width, height, depth, color, compression, filtering, interlace = struct.unpack(">IIBBBBB", ihdr)
                if (not 1 <= width <= MAX_DIMENSION or not 1 <= height <= MAX_DIMENSION
                        or width * height > MAX_PIXELS or depth not in _VALID_DEPTHS.get(color, set())
                        or compression != 0 or filtering != 0 or interlace not in (0, 1)):
                    raise ValueError("invalid or excessive PNG dimensions/format")
                seen_ihdr = True
            elif kind == b"PLTE":
                seen_plte = True
            elif kind == b"IDAT":
                seen_idat = True
            elif seen_idat and kind != b"IEND":
                idat_ended = True
            if kind == b"IEND":
                seen_iend = True
                if offset != size:
                    raise ValueError("trailing bytes after PNG IEND")
                break
        if not seen_iend:
            raise ValueError("PNG missing IEND")

        # Detect concurrent replacement, truncation, append or modification.
        # Parsing and hashing used the same open descriptor throughout.
        after = os.fstat(stream.fileno())
        before_state = (before.st_dev, before.st_ino, before.st_size,
                        before.st_mtime_ns, before.st_ctime_ns)
        after_state = (after.st_dev, after.st_ino, after.st_size,
                       after.st_mtime_ns, after.st_ctime_ns)
        if after_state != before_state:
            raise ValueError("PNG changed during inspection")
    return digest.hexdigest(), size
