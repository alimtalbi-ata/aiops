"""Deterministic binding of *synthetic* STAR events to NOC screenshots.

Hash bindings are for reproducible demo fixture integrity, never runtime proof.
"""
from __future__ import annotations
import hashlib
import json
from demo.noc_star_cue_map import bind_noc_evidence_to_star

def bind_synthetic_star_events(index:dict,events:list)->dict:
    mapping=bind_noc_evidence_to_star(index)
    if not isinstance(events,list) or len(events)!=9:
        raise ValueError("nine synthetic STAR steps required")
    cues=mapping["cues"]
    if [row.get("cue") for row in events if isinstance(row,dict)]!=cues:
        raise ValueError("ordered cue identity mismatch")
    run_ids=set();items=[]
    for row in events:
        if not isinstance(row,dict) or set(row)!={"cue","run_id","incident_id","event_id","source_type","payload"}:
            raise ValueError("unknown synthetic event fields")
        if row["source_type"]!="SYNTHETIC" or not isinstance(row["payload"],dict):
            raise ValueError("untrusted event origin")
        ids=(row["run_id"],row["incident_id"],row["event_id"])
        if not all(isinstance(v,str) and 1<=len(v)<=100 and all(c.isalnum() or c in "_-" for c in v) for v in ids):
            raise ValueError("invalid event identifiers")
        run_ids.add(ids[:2])
        payload=json.dumps(row,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False).encode("utf-8")
        items.append({"cue":row["cue"],"event_id":row["event_id"],
                      "event_sha256":hashlib.sha256(payload).hexdigest(),
                      "source_type":"SYNTHETIC","runtime_authenticated":False})
    if len(run_ids)!=1 or len(set(x["event_id"] for x in items))!=9:
        raise ValueError("mixed run or duplicate STAR event")
    run_id,incident_id=next(iter(run_ids))
    bindings=[{"file":item["file"],"sha256":item["sha256"],
               "illustrative_cues":item["cue_ids"],
               "synthetic_event_ids":[e["event_id"] for e in items if e["cue"] in item["cue_ids"]],
               "relationship":"ILLUSTRATIVE_SYNTHETIC_HASH_BINDING",
               "runtime_authenticated":False} for item in mapping["bindings"]]
    return {"schema":"aiops-noc-synthetic-star-hash-link-v1",
            "run_id":run_id,"incident_id":incident_id,"events":items,
            "captures":bindings,"runtime_authenticated":False,
            "verified_runtime_event_links":0,"live_remediation_authorized":False}
