"""Validate NOC browser screenshots before admission to an OFFLINE_TEST evidence set.

No artifact can be promoted as runtime-authenticated evidence.
"""
from __future__ import annotations
import json
import re
from pathlib import Path
from demo.star_png_integrity import inspect_png

EXPECTED={"unified.png","synthetic.png","checkmk-export.png"}
SHA=re.compile(r"^[0-9a-f]{64}$")

def verify_noc_offline_browser_evidence(folder:Path)->dict:
    folder=Path(folder)
    if folder.is_symlink() or not folder.is_dir():
        raise ValueError("unsafe evidence directory")
    file=folder/"manifest.json"
    if file.is_symlink() or not file.is_file() or file.stat().st_size>30_000:
        raise ValueError("invalid manifest")
    manifest=json.loads(file.read_text(encoding="utf-8"))
    if (not isinstance(manifest,dict) or manifest.get("schema")!="aiops-noc-offline-browser-artifacts-v1"
            or manifest.get("source")!="SYNTHETIC_AND_UNVERIFIED_EXPORTS"
            or manifest.get("runtime_proof_count")!=0 or manifest.get("live_remediation_authorized") is not False):
        raise ValueError("untrusted evidence claims")
    captures=manifest.get("captures")
    if not isinstance(captures,list) or len(captures)!=3:
        raise ValueError("invalid capture list")
    seen=set()
    for row in captures:
        if not isinstance(row,dict) or set(row)!={"file","sha256","size_bytes","evidence_type","runtime_authenticated"}:
            raise ValueError("invalid capture metadata")
        name=row["file"]
        if name not in EXPECTED or name in seen or row["evidence_type"]!="LOCAL_OFFLINE_BROWSER_RENDER" or row["runtime_authenticated"] is not False:
            raise ValueError("untrusted screenshot")
        if type(row["size_bytes"]) is not int or row["size_bytes"]<100 or not isinstance(row["sha256"],str) or not SHA.fullmatch(row["sha256"]):
            raise ValueError("bad capture hash metadata")
        seen.add(name)
        png=folder/name
        if png.is_symlink() or not png.is_file():
            raise ValueError("missing/symlink capture")
        digest,size=inspect_png(png)
        if (digest,size)!=(row["sha256"],row["size_bytes"]):
            raise ValueError("altered capture")
    if seen!=EXPECTED or set(p.name for p in folder.iterdir())!=EXPECTED|{"manifest.json"}:
        raise ValueError("missing or unexpected evidence file")
    return {"schema":"aiops-noc-evidence-verification-v1",
            "evidence_class":"OFFLINE_TEST","verified_captures":3,
            "runtime_authenticated":False,"live_remediation_authorized":False}
