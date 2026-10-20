#!/usr/bin/env python3
"""Read-only validation of AIOps private backup sets before any restore."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import stat
import sys
import tarfile

REQUIRED = {
    "aiops.dump","n8n.dump","temporal.dump","temporal_visibility.dump",
    "glpi-mariadb.sql","aiops2-n8n-data.tar.gz","aiops2-glpi-data.tar.gz",
    "aiops2-grafana-data.tar.gz","aiops2-prometheus-data.tar.gz",
    ".env.private","git-head.txt","BACKUP-MANIFEST.json",
}

def file_sha256(path: Path) -> str:
    h=hashlib.sha256()
    with path.open("rb") as data:
        for chunk in iter(lambda:data.read(1024*1024),b""):
            h.update(chunk)
    return h.hexdigest()

def verify_backup(folder: Path, expected_stack: str) -> dict:
    if not folder.is_dir():
        raise ValueError("backup_directory_missing")
    if (folder/".BACKUP_INCOMPLETE").exists():
        raise ValueError("backup_incomplete")
    manifest_file=folder/"BACKUP-MANIFEST.json"
    sha_file=folder/"SHA256SUMS"
    if not manifest_file.is_file() or not sha_file.is_file():
        raise ValueError("backup_manifest_or_checksums_missing")
    data=json.loads(manifest_file.read_text(encoding="utf-8"))
    if data.get("format_version")!=2 or data.get("backup_status")!="COMPLETE":
        raise ValueError("unsupported_or_incomplete_backup_format")
    if data.get("stack_id")!=expected_stack:
        raise ValueError("backup_stack_identity_mismatch")
    if data.get("contains_secrets") is not True:
        raise ValueError("private_backup_marker_missing")
    declared=set(data.get("files",[]))|{"BACKUP-MANIFEST.json"}
    if not REQUIRED.issubset(declared):
        raise ValueError("backup_manifest_missing_required_files")
    checksums={}
    for line in sha_file.read_text(encoding="utf-8").splitlines():
        match=re.fullmatch(r"([0-9a-f]{64})  \.\/([^\n]+)",line)
        if not match:
            raise ValueError("invalid_checksum_line")
        name=match.group(2)
        path=PurePosixPath(name)
        if path.is_absolute() or len(path.parts)!=1 or name in checksums:
            raise ValueError("unsafe_or_repeated_checksum_target")
        checksums[name]=match.group(1)
    if declared!=set(checksums):
        raise ValueError("checksum_manifest_coverage_incomplete")
    for name,expected_digest in checksums.items():
        path=folder/name
        if path.is_symlink():
            raise ValueError("backup_symlink_file_forbidden:"+name)
        if not path.is_file() or path.stat().st_size==0:
            raise ValueError("missing_or_empty_backup_file:"+name)
        if file_sha256(path)!=expected_digest:
            raise ValueError("backup_checksum_mismatch:"+name)
    for name in ("aiops.dump","n8n.dump","temporal.dump","temporal_visibility.dump"):
        with (folder/name).open("rb") as f:
            if f.read(5)!=b"PGDMP":
                raise ValueError("postgres_custom_dump_invalid:"+name)
    for suffix in ("n8n-data","glpi-data","grafana-data","prometheus-data"):
        name="aiops2-"+suffix+".tar.gz"
        # Restore uses privileged tar into stack-owned volumes. Reject special
        # files and links entirely rather than trusting tar extraction semantics.
        # Bounds are checked before any destination volume is mutated.
        member_count=0
        declared_bytes=0
        with tarfile.open(folder/name,mode="r|gz") as tar:
            for member in tar:
                member_count+=1
                if member_count>1000000:
                    raise ValueError("backup_tar_member_limit:"+name)
                path=PurePosixPath(member.name)
                if path.is_absolute() or ".." in path.parts or "\\\\" in member.name:
                    raise ValueError("unsafe_tar_member:"+name)
                if not (member.isfile() or member.isdir()):
                    raise ValueError("backup_tar_special_member_forbidden:"+name)
                if member.isfile():
                    declared_bytes+=member.size
                    if member.size>100*1024**3 or declared_bytes>500*1024**3:
                        raise ValueError("backup_tar_size_limit:"+name)
    return {"result":"PASS","stack_id":expected_stack,"format_version":2,
            "files_verified":len(checksums),"application_consistent":data.get("application_consistent",False)}

if __name__=="__main__":
    if len(sys.argv)!=3:
        print("Usage: python3 deploy/verify_backup.py <backup-directory> <target-stack-id>",file=sys.stderr)
        raise SystemExit(2)
    try:
        report=verify_backup(Path(sys.argv[1]),sys.argv[2])
        print("BACKUP_VERIFICATION=PASS|stack_id="+report["stack_id"]+"|files="+str(report["files_verified"]))
        if not report["application_consistent"]:
            print("WARNING|online_volumes_are_not_application_consistent")
    except Exception as exc:
        print("BACKUP_VERIFICATION=FAIL|"+str(exc),file=sys.stderr)
        raise SystemExit(1)
