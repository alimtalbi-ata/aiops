"""Map reviewed offline NOC capture classes to STAR demo cues; no runtime claims."""
from __future__ import annotations
from demo.noc_evidence_center import EXPECTED

CUES=("detect","correlate","enrich","analyze","ticket","approve","simulate","verify","close")
CAPTURE_CUES={
 "unified.png":("detect","correlate","verify"),
 "synthetic.png":("enrich","analyze","simulate"),
 "checkmk-export.png":("detect","verify"),
}

def bind_noc_evidence_to_star(index:dict)->dict:
    from demo.noc_evidence_center import render_noc_evidence_center
    render_noc_evidence_center(index)  # strict metadata / classification validation
    mapped=[]
    for entry in index["entries"]:
        filename=entry["file"]
        mapped.append({"file":filename,"sha256":entry["sha256"],"cue_ids":list(CAPTURE_CUES[filename]),
                       "relationship":"ILLUSTRATIVE_ONLY","evidence_class":"OFFLINE_TEST",
                       "event_bound":False,"runtime_authenticated":False})
    return {"schema":"aiops-noc-star-offline-cue-map-v1","cues":list(CUES),
            "bindings":sorted(mapped,key=lambda e:e["file"]),
            "run_id":None,"incident_id":None,"verified_event_links":0,
            "source":"OFFLINE_DEMO_ONLY","runtime_authenticated":False}
