#!/usr/bin/env python3
"""ACME synthetic Evidence importer. Dry-run by default, explicit --commit required."""
import argparse,hashlib,json,os,sys
from pathlib import Path

ALLOWED_KINDS={"metric","log","trace"}

def prepare(rows):
    prepared=[]
    seen=set()
    for index,row in enumerate(rows,1):
        if not isinstance(row,dict) or row.get("scope")!="ACME" or row.get("synthetic") is not True:
            raise ValueError(f"row {index}: not explicit synthetic ACME data")
        if row.get("kind") not in ALLOWED_KINDS or not str(row.get("ci_id","")).startswith("ACME-"):
            raise ValueError(f"row {index}: invalid type or CI scope")
        if not row.get("timestamp") or not row.get("correlation_id"):
            raise ValueError(f"row {index}: missing time or correlation")
        canonical=json.dumps(row,sort_keys=True,separators=(",",":"),ensure_ascii=False)
        digest=hashlib.sha256(canonical.encode()).hexdigest()
        if digest in seen:
            raise ValueError(f"row {index}: duplicate in import file")
        seen.add(digest)
        prepared.append({"source":"acme-simulator-v293","external_id":"SIM-"+digest[:40],
            "observed_at":row["timestamp"],
            "claim":str(row.get("message") or (str(row.get("metric") or row.get("operation"))+"="+str(row.get("value",row.get("duration_ms","")))))[:8192],
            "confidence":0.8,
            "provenance":{"scope":"ACME","synthetic":True,"record_type":"synthetic_telemetry",
              "scenario":row.get("scenario"),"correlation_id":row["correlation_id"],
              "ci_id":row["ci_id"],"kind":row["kind"],"generator":row.get("source")},
            "payload":row})
    return prepared

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("file",type=Path)
    parser.add_argument("--commit",action="store_true",help="Explicitly write to Evidence API")
    parser.add_argument("--endpoint",default="http://127.0.0.1:812")
    opts=parser.parse_args()
    rows=[json.loads(line) for line in opts.file.read_text().splitlines() if line.strip()]
    prepared=prepare(rows)
    print(json.dumps({"mode":"COMMIT" if opts.commit else "DRY_RUN","scope":"ACME",
                      "records":len(prepared),"first_external_id":prepared[0]["external_id"] if prepared else None}))
    if not opts.commit:
        return
    import requests
    token=os.environ.get("AIOPS_INTERNAL_TOKEN")
    if not token:
        raise SystemExit("BLOCK: AIOPS_INTERNAL_TOKEN required for --commit")
    if not opts.endpoint.startswith("http://127.0.0.1:") and not opts.endpoint.startswith("http://localhost:"):
        raise SystemExit("BLOCK: endpoint must be loopback; use a controlled local forwarding proxy")
    inserted=deduplicated=0
    for i,item in enumerate(prepared,1):
        response=requests.post(opts.endpoint.rstrip("/")+"/api/evidence",json=item,
              headers={"Authorization":"Bearer "+token},timeout=15)
        response.raise_for_status()
        answer=response.json()
        inserted+=int(not answer.get("deduplicated",False))
        deduplicated+=int(bool(answer.get("deduplicated",False)))
    print(json.dumps({"inserted":inserted,"deduplicated":deduplicated,"total":len(prepared)}))

if __name__=="__main__":
    main()
