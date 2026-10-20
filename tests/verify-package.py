#!/usr/bin/env python3
"""Verify a cumulative AIOps release ZIP without extracting untrusted files."""
from __future__ import annotations
import hashlib
from pathlib import Path, PurePosixPath
import re
import sys
import zipfile


def sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def verify(archive: Path) -> dict:
    if not archive.is_file():
        raise ValueError("archive_missing")
    outside=archive.with_suffix(archive.suffix+".sha256")
    if not outside.is_file():
        raise ValueError("outer_checksum_missing")
    checksum_line=outside.read_text(encoding="utf-8").strip()
    match=re.fullmatch(r"([0-9a-f]{64})  ([^/\\]+)", checksum_line)
    if not match or match.group(2)!=archive.name:
        raise ValueError("nonportable_or_invalid_outer_checksum")
    if match.group(1)!=sha256(archive.read_bytes()):
        raise ValueError("outer_checksum_mismatch")
    with zipfile.ZipFile(archive) as z:
        bad=z.testzip()
        if bad:
            raise ValueError("zip_crc_failed:"+bad)
        names=[info.filename for info in z.infolist() if not info.is_dir()]
        if len(set(names))!=len(names):
            raise ValueError("duplicate_archive_names")
        for name in names:
            p=PurePosixPath(name)
            if name.startswith("/") or ".." in p.parts or "\\" in name:
                raise ValueError("unsafe_archive_path:"+name)
            if name==".env" or name.endswith("/.env") or name.startswith((".git/","backups/","reports/")):
                raise ValueError("forbidden_archive_content:"+name)
        required={"RELEASE-MANIFEST.txt","FILES-SHA256SUMS","compose.yml",
                  "deploy/install.sh","deploy/migrate.sh","app/worker/workflow.py",
                  "db/migrations/009_ai_decision_ledger.sql",
                  "db/migrations/010_evidence_identity.sql",
                  "deploy/verify_backup.py","tests/evidence-e2e.sh",
                  "tests/runtime-e2e.sh","tests/model-evaluation-e2e.sh",
                  "09-Qualification/ai-core-evaluation.json"}
        if not required.issubset(names):
            raise ValueError("required_files_missing:"+",".join(sorted(required-set(names))))
        manifest=z.read("FILES-SHA256SUMS").decode("utf-8")
        found={}
        for line in manifest.splitlines():
            match=re.fullmatch(r"([0-9a-f]{64})  \.\/([^\n]+)",line)
            if not match:
                raise ValueError("invalid_manifest_entry:"+line[:100])
            path=match.group(2)
            if path in found or path=="FILES-SHA256SUMS":
                raise ValueError("duplicate_or_self_referential_manifest_entry")
            found[path]=match.group(1)
        expected=set(names)-{"FILES-SHA256SUMS"}
        if set(found)!=expected:
            raise ValueError("manifest_coverage_mismatch")
        for name,digest in found.items():
            if sha256(z.read(name))!=digest:
                raise ValueError("manifest_checksum_mismatch:"+name)
        release=z.read("RELEASE-MANIFEST.txt").decode("utf-8")
        if "qualification=CI-runtime-e2e-PASS" not in release:
            raise ValueError("runtime_qualification_not_passed")
        if "synthetic_analyst_critic_quality=PASS" not in release:
            raise ValueError("synthetic_ai_qualification_not_passed")
        if "real_model_qualification=NOT_RUN" not in release:
            raise ValueError("real_model_qualification_must_be_explicit")
    return {"archive":archive.name,"sha256":sha256(archive.read_bytes()),
            "files_verified":len(found),"status":"PASS",
            "qualification":"synthetic CI integration, not production"}


if __name__=="__main__":
    if len(sys.argv)!=2:
        print("USAGE: python3 tests/verify-package.py <path-to-ZIP>")
        raise SystemExit(2)
    try:
        result=verify(Path(sys.argv[1]))
        print("PACKAGE_VERIFICATION=PASS|files="+str(result["files_verified"])+"|sha256="+result["sha256"])
    except Exception as exc:
        print("PACKAGE_VERIFICATION=FAIL|reason="+str(exc),file=sys.stderr)
        raise SystemExit(1)
