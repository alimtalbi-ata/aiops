"""Deterministic uncompressed LAB OCI archive; strict extraction, not a signature."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import sys
import tarfile
from oci_transport import MAX_BLOB, MAX_TOTAL, require, valid_digest, verify

MAX_MEMBERS = 10 * (256 + 2) + 1
MAX_ARCHIVE = MAX_TOTAL + 1024**2 + MAX_MEMBERS * 1024 + 10240


def open_regular(path):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    f = os.fdopen(fd, 'rb')
    if not stat.S_ISREG(os.fstat(f.fileno()).st_mode):
        f.close()
        raise ValueError('regular file required')
    return f


def sha_file(f):
    f.seek(0)
    result = 'sha256:' + hashlib.file_digest(f, 'sha256').hexdigest()
    f.seek(0)
    return result


def member_identity(name, expected_bom):
    if name == 'image-bom.json':
        return expected_bom, 1024**2
    require(re.fullmatch(r'blobs/[a-f0-9]{64}', name) is not None, 'unexpected archive path')
    return 'sha256:' + name[6:], MAX_BLOB


class HashedReader:
    def __init__(self, stream):
        self.stream = stream
        self.hash = hashlib.sha256()
    def read(self, size):
        raw = self.stream.read(size)
        self.hash.update(raw)
        return raw
    def digest(self):
        return 'sha256:' + self.hash.hexdigest()


def pack(root, archive, expected_bom):
    receipt = verify(root, expected_bom)
    names = ['image-bom.json'] + ['blobs/' + p.name for p in sorted((root / 'blobs').iterdir())]
    require(len(names) <= MAX_MEMBERS, 'too many members')
    fd = os.open(archive, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        total = 0
        with os.fdopen(fd, 'wb') as out, tarfile.open(fileobj=out, mode='w', format=tarfile.USTAR_FORMAT) as tar:
            for name in names:
                expected, limit = member_identity(name, expected_bom)
                with open_regular(root / name) as f:
                    size = os.fstat(f.fileno()).st_size
                    total += size
                    require(0 < size <= limit and total <= MAX_TOTAL + 1024**2, 'invalid member size')
                    info = tarfile.TarInfo(name)
                    info.size, info.mode, info.mtime = size, 0o600, 0
                    reader = HashedReader(f)
                    tar.addfile(info, reader)
                    require(reader.digest() == expected and not f.read(1), 'source changed while packing')
        with open_regular(archive) as f:
            require(os.fstat(f.fileno()).st_size <= MAX_ARCHIVE, 'archive too large')
            archive_sha = sha_file(f)
    except BaseException:
        archive.unlink()
        raise
    return {**receipt, 'classification': 'V3_E17_OCI_ENVELOPE', 'archive_sha256': archive_sha}


def unpack(archive, root, expected_archive, expected_bom):
    require(valid_digest(expected_archive) and valid_digest(expected_bom), 'expected digests required')
    with open_regular(archive) as f:
        require(0 < os.fstat(f.fileno()).st_size <= MAX_ARCHIVE, 'invalid archive size')
        require(sha_file(f) == expected_archive, 'archive digest mismatch')
        root.mkdir(mode=0o700)
        try:
            (root / 'blobs').mkdir(mode=0o700)
            seen = set()
            total = 0
            with tarfile.open(fileobj=f, mode='r:') as tar:
                for member in tar:
                    name = member.name
                    expected, limit = member_identity(name, expected_bom)
                    require(member.type == tarfile.REGTYPE and not member.pax_headers and not member.sparse and not member.linkname, 'noncanonical archive member')
                    require(name not in seen and len(seen) < MAX_MEMBERS, 'duplicate or excessive members')
                    require(seen or name == 'image-bom.json', 'BOM must be first')
                    total += member.size
                    require(0 < member.size <= limit and total <= MAX_TOTAL + 1024**2, 'invalid member size')
                    stream = tar.extractfile(member)
                    require(stream is not None, 'missing member data')
                    fd = os.open(root / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
                    with stream, os.fdopen(fd, 'wb') as out:
                        reader = HashedReader(stream)
                        remaining = member.size
                        while remaining:
                            chunk = reader.read(min(remaining, 1024**2))
                            require(bool(chunk), 'truncated member')
                            out.write(chunk)
                            remaining -= len(chunk)
                        require(reader.digest() == expected, 'member digest mismatch')
                    seen.add(name)
            require(sha_file(f) == expected_archive, 'archive changed during extraction')
            receipt = verify(root, expected_bom)
        except BaseException:
            shutil.rmtree(root)
            raise
    return {**receipt, 'classification': 'V3_E17_OCI_ENVELOPE', 'archive_sha256': expected_archive}


if __name__ == '__main__':
    mode, *args = sys.argv[1:]
    if mode == 'pack' and len(args) == 3:
        result = pack(Path(args[0]), Path(args[1]), args[2])
    elif mode == 'unpack' and len(args) == 4:
        result = unpack(Path(args[0]), Path(args[1]), args[2], args[3])
    else:
        raise SystemExit('pack ROOT NEW_TAR EXPECTED_BOM | unpack TAR NEW_ROOT EXPECTED_TAR EXPECTED_BOM')
    print(json.dumps(result, sort_keys=True))
