#!/usr/bin/env python3
"""Read-only provenance/dependency audit for the archived V2.13.4 hybrid replay.

This tool deliberately does not import or execute historical replay code and
never creates, repairs, or overwrites files.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

EXPECTED = {
    "tools/build_real_replay.py": {
        "sha256": "f71a568f4229402a6f6b5238552efbdd18fa41320c8c285afedc386812bbb97d",
        "role": "historical replay model builder",
    },
    "tests/test_replay.py": {
        "sha256": "e1fadcf8c20ab19ba1e696aa11237f42ec300a64ce9745b496023648eaaef8aa",
        "role": "historical replay regression tests",
    },
}


def audit(root: Path) -> dict:
    """Report expected historical members without following symlinks."""
    root = root.resolve()
    members = []
    for relative, expected in EXPECTED.items():
        path = root / relative
        row = {
            "path": relative,
            "role": expected["role"],
            "expected_sha256": expected["sha256"],
            "observed_sha256": None,
            "status": "MISSING",
            "execution_performed": False,
        }
        if path.is_symlink():
            row["status"] = "REJECTED_SYMLINK"
        elif path.exists():
            if not path.is_file():
                row["status"] = "REJECTED_NOT_REGULAR_FILE"
            else:
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
                row["observed_sha256"] = digest
                row["status"] = "MATCH" if digest == expected["sha256"] else "HASH_MISMATCH"
        members.append(row)

    assembler = root / "tools/assemble_hybrid.py"
    assembler_row = {
        "path": "tools/assemble_hybrid.py",
        "status": "MISSING",
        "observed_sha256": None,
        "execution_performed": False,
    }
    if assembler.is_symlink():
        assembler_row["status"] = "REJECTED_SYMLINK"
    elif assembler.is_file():
        assembler_row["observed_sha256"] = hashlib.sha256(assembler.read_bytes()).hexdigest()
        assembler_row["status"] = "PRESENT_UNEXECUTED"

    complete = all(row["status"] == "MATCH" for row in members)
    return {
        "schema_version": 1,
        "archive_lineage": "AIOPS-V2.13.4-HYBRID-REPLAY-STAR.zip",
        "scope": "local source presence and SHA-256 only",
        "source_execution_performed": False,
        "runtime_qualification": False,
        "recovery_complete": complete,
        "members": members,
        "assembler": assembler_row,
        "decision": "READY_FOR_SEPARATE_REVIEW" if complete else "RECOVERY_INCOMPLETE",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, help="optional new JSON output path; existing files are refused")
    args = parser.parse_args()
    result = audit(args.root)
    payload = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        if args.output.exists() or args.output.is_symlink():
            parser.error("refusing to overwrite existing output")
        args.output.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")
    return 0 if result["recovery_complete"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
