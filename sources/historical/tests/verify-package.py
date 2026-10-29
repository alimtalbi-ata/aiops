#!/usr/bin/env python3
"""Verify a cumulative AIOps release ZIP without extracting untrusted files."""
from __future__ import annotations
import hashlib
import json
import stat
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
        # Bound extraction cost even when SHA-256 and CRC are valid. ZIP metadata
        # is untrusted; reject links, encryption, duplicates and zip bombs.
        entries=z.infolist()
        MAX_ENTRIES=10000
        MAX_SINGLE_FILE=128*1024*1024
        MAX_TOTAL_UNCOMPRESSED=1024*1024*1024
        MAX_RATIO=250
        if len(entries)>MAX_ENTRIES:
            raise ValueError("archive_entry_limit_exceeded")
        total_size=0
        for info in entries:
            mode=(info.external_attr >> 16) & 0xffff
            if stat.S_IFMT(mode)==stat.S_IFLNK:
                raise ValueError("archive_symlink_forbidden:"+info.filename)
            if info.flag_bits & 1:
                raise ValueError("encrypted_archive_entry:"+info.filename)
            if info.is_dir():
                continue
            if info.file_size>MAX_SINGLE_FILE:
                raise ValueError("archive_file_size_limit_exceeded:"+info.filename)
            if info.file_size > MAX_RATIO*max(1,info.compress_size) and info.file_size>1024*1024:
                raise ValueError("archive_compression_ratio_limit_exceeded:"+info.filename)
            total_size+=info.file_size
            if total_size>MAX_TOTAL_UNCOMPRESSED:
                raise ValueError("archive_total_size_limit_exceeded")
        bad=z.testzip()
        if bad:
            raise ValueError("zip_crc_failed:"+bad)
        names=[info.filename for info in entries if not info.is_dir()]
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
                  "deploy/package_tree.py","deploy/plan_isolation.py"}
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
        meta={}
        for line in release.splitlines():
            if "=" not in line:
                raise ValueError("invalid_release_manifest_entry")
            key,value=line.split("=",1)
            if key in meta:
                raise ValueError("duplicate_release_manifest_key")
            meta[key]=value
        if meta.get("real_model_qualification")!="NOT_RUN":
            raise ValueError("real_model_qualification_must_be_explicit")
        if meta.get("production_qualification")!="NOT_RUN":
            raise ValueError("production_qualification_must_be_explicit")
        declared=meta.get("qualification")
        if declared=="CI-runtime-e2e-PASS":
            required_reports={"09-Qualification/ai-core-evaluation.json"}
            runtime_reports=[item for item in names if item.startswith("09-Qualification/runtime-e2e-") and item.endswith(".json")]
            if not required_reports.issubset(names) or not runtime_reports:
                raise ValueError("qualified_release_missing_ci_evidence")
            if meta.get("synthetic_analyst_critic_quality")!="PASS" or meta.get("ci_evidence_carried")!="yes":
                raise ValueError("qualified_release_manifest_inconsistent")
            evaluation=json.loads(z.read("09-Qualification/ai-core-evaluation.json"))
            if (evaluation.get("result")!="PASS" or
                evaluation.get("qualification_kind")!="deterministic-integration-fixture" or
                evaluation.get("ledger_persistence",{}).get("status")!="PASS"):
                raise ValueError("model_evaluation_ci_evidence_invalid")
            for report_name in runtime_reports:
                evidence=json.loads(z.read(report_name))
                if evidence.get("result")!="PASS" or evidence.get("live_execution")!="disabled":
                    raise ValueError("runtime_ci_evidence_invalid")
            qualification="SYNTHETIC_CI_PASS"
        elif declared=="static-unit-only":
            if meta.get("synthetic_analyst_critic_quality")!="NOT_RUN" or meta.get("ci_evidence_carried")!="no":
                raise ValueError("source_only_manifest_inconsistent")
            if any(name.startswith("09-Qualification/") for name in names):
                raise ValueError("unqualified_source_cannot_carry_ci_reports")
            qualification="UNQUALIFIED_SOURCE_ONLY"
        else:
            raise ValueError("unknown_release_qualification_status")
    return {"archive":archive.name,"sha256":sha256(archive.read_bytes()),
            "files_verified":len(found),"status":"PASS",
            "qualification":qualification}


if __name__=="__main__":
    if len(sys.argv)!=2:
        print("USAGE: python3 tests/verify-package.py <path-to-ZIP>")
        raise SystemExit(2)
    try:
        result=verify(Path(sys.argv[1]))
        print("PACKAGE_VERIFICATION=PASS|qualification="+result["qualification"]+"|files="+str(result["files_verified"])+"|sha256="+result["sha256"])
    except Exception as exc:
        print("PACKAGE_VERIFICATION=FAIL|reason="+str(exc),file=sys.stderr)
        raise SystemExit(1)
