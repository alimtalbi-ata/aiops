#!/usr/bin/env bash
# Replay-safety end-to-end against the isolated Compose Evidence service.
# No live adapter, remediation endpoint or production CI is touched.
set -Eeuo pipefail
cd "$(dirname "$0")/.."
docker compose --env-file .env exec -T aiops2-worker python - <<'PY'
import os
import uuid
import requests

base=os.getenv("EVIDENCE_URL","http://aiops2-evidence:812").rstrip("/")
token=os.environ["AIOPS_INTERNAL_TOKEN"]
headers={"Authorization":"Bearer "+token}
uid=uuid.uuid4().hex
run_id="CI-RUN-"+uid
body={
 "source":"ci-replay-e2e",
 "external_id":run_id+":paths",
 "observed_at":"2026-10-20T08:00:00+02:00",
 "claim":"Synthetic FC path degraded",
 "confidence":0.8,
 "provenance":{"run_id":run_id,"synthetic":True,"stage":"OBSERVE"},
 "payload":{"node_id":"ACME-SAN-FABRIC-A","active_paths":1,"total_paths":4}
}
a=requests.post(base+"/api/evidence",headers=headers,json=body,timeout=15)
a.raise_for_status()
first=a.json()
assert first["deduplicated"] is False,first
b=requests.post(base+"/api/evidence",headers=headers,json=body,timeout=15)
b.raise_for_status()
replay=b.json()
assert replay["deduplicated"] is True,replay
assert replay["evidence_id"]==first["evidence_id"],(first,replay)
changed=dict(body,claim="Modified claim on existing external identity")
conflict=requests.post(base+"/api/evidence",headers=headers,json=changed,timeout=15)
assert conflict.status_code==409,(conflict.status_code,conflict.text[:200])
independent=dict(body,external_id=run_id+":paths-independent",
    provenance={**body["provenance"],"run_id":run_id+"-NEW"})
independent["external_id"]=run_id+"-NEW:paths"
different=requests.post(base+"/api/evidence",headers=headers,json=independent,timeout=15)
different.raise_for_status()
assert different.json()["evidence_id"]!=first["evidence_id"]
read=requests.get(base+"/api/evidence",headers=headers,params={"run_id":run_id},timeout=15)
read.raise_for_status()
ids={row["evidence_id"] for row in read.json()["items"]}
assert first["evidence_id"] in ids,ids
assert different.json()["evidence_id"] not in ids,ids
print("EVIDENCE_REPLAY_E2E=PASS|exact_retry=true|collision=409|cross_run_isolation=true")
PY
