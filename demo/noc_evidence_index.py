"""Index verified NOC browser evidence without promoting it to runtime evidence."""
from __future__ import annotations
import json
from pathlib import Path
from demo.noc_browser_evidence_gate import verify_noc_offline_browser_evidence

def build_noc_evidence_index(folder:Path)->dict:
    verified=verify_noc_offline_browser_evidence(folder)
    manifest=json.loads((Path(folder)/"manifest.json").read_text(encoding="utf-8"))
    entries=[]
    for item in sorted(manifest["captures"],key=lambda a:a["file"]):
        entries.append({"id":"noc-offline-"+item["file"].removesuffix(".png"),
                        "file":item["file"],"sha256":item["sha256"],
                        "size_bytes":item["size_bytes"],"class":"OFFLINE_TEST",
                        "source":"LOCAL_OFFLINE_BROWSER_RENDER",
                        "runtime_authenticated":False,"promotable_to_runtime":False})
    return {"schema":"aiops-noc-evidence-index-v1","entries":entries,
            "counts":{"OFFLINE_TEST":verified["verified_captures"],
                      "OBSERVATION":0,"RUNTIME_EVIDENCE":0},
            "runtime_authenticated":False,
            "live_remediation_authorized":False}
