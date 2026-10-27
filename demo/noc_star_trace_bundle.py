"""Reproducible nine-step offline STAR timeline and NOC evidence bundle."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from demo.noc_star_cue_map import CUES
from demo.noc_star_event_binding import bind_synthetic_star_events
from demo.noc_star_trace_page import render_noc_star_trace

def make_synthetic_star_events()->list[dict]:
    return [{"cue":cue,"run_id":"RUN-ACME-OFFLINE-STAR",
             "incident_id":"INC-ACME-SAN-LOSS","event_id":f"EV-ACME-{n:02d}",
             "source_type":"SYNTHETIC",
             "payload":{"sequence":n,"scenario":"ACME_SAN_SIMULATION","runtime":False}}
            for n,cue in enumerate(CUES,1)]

def generate_star_trace_package(index:dict)->tuple[dict,str]:
    events=make_synthetic_star_events()
    return bind_synthetic_star_events(index,events),render_noc_star_trace(index,events)

def main()->None:
    p=argparse.ArgumentParser()
    p.add_argument("evidence_index",type=Path)
    p.add_argument("--output-dir",type=Path,required=True)
    a=p.parse_args()
    index=json.loads(a.evidence_index.read_text(encoding="utf-8"))
    binding,page=generate_star_trace_package(index)
    if not a.output_dir.is_dir():
        raise ValueError("output directory must exist")
    documents={
      "star-trace.html":page,
      "star-event-binding.json":json.dumps(binding,indent=2,ensure_ascii=False)+"\n",
      "star-events.json":json.dumps(make_synthetic_star_events(),indent=2,ensure_ascii=False)+"\n"}
    if any((a.output_dir/name).exists() for name in documents):
        raise FileExistsError("refusing to overwrite evidence")
    for name,content in documents.items():
        with (a.output_dir/name).open("x",encoding="utf-8") as output:output.write(content)

if __name__=="__main__":main()
