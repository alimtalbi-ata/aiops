"""Read-only verifier for a downloaded AIOPS2 synthetic CI ZIP.

A manifest and hashes are self-asserted; canonical fixture comparison is required.
Never extract untrusted ZIP entries to disk.
"""
import argparse
import io
import json
import sys
import tempfile
import zipfile
from pathlib import Path

from package_aiops2_demo_evidence import verify_package

EXPECTED = {"acceptance.json", "cockpit.json", "cockpit.html", "manifest.json"}
MAX_FILE = 2 * 1024 * 1024
MAX_TOTAL = 4 * 1024 * 1024


def verify_zip(path):
    with zipfile.ZipFile(path) as archive:
        infos = archive.infolist()
        names = [info.filename for info in infos]
        if (len(infos) != 4 or set(names) != EXPECTED
                or len(set(names)) != len(names)
                or any(info.is_dir() or info.file_size > MAX_FILE
                       or info.file_size < 0 or info.flag_bits & 0x1
                       for info in infos)
                or sum(info.file_size for info in infos) > MAX_TOTAL):
            return False
        # zipfile's CRC and length checks are additional to the manifest.
        with tempfile.TemporaryDirectory(prefix="aiops2-demo-verify-") as directory:
            destination = Path(directory)
            for info in infos:
                data = archive.read(info)
                if len(data) != info.file_size:
                    return False
                (destination / info.filename).write_bytes(data)
            return verify_package(destination)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("zip_path", type=Path)
    args = parser.parse_args()
    try:
        valid = verify_zip(args.zip_path)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError,
            zipfile.BadZipFile, EOFError, RuntimeError):
        valid = False
    if not valid:
        print("BLOCKED: invalid or noncanonical synthetic demo ZIP", file=sys.stderr)
        raise SystemExit(1)
    print("PASS: canonical synthetic demo ZIP; runtime evidence remains UNKNOWN")
