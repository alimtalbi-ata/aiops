"""Read-only lab context; legacy endpoints are not tenant-qualified."""
import hashlib
import http.client
import json
import re
from rca_preview import preview
from evidence_retrieval import validated_reference

def get(port, path):
    if type(port) is not int or not 1024 <= port <= 65535 or port in (7770,7777,7790):
        raise ValueError("invalid lab port")
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        conn.request("GET", path)
        response = conn.getresponse()
        raw = response.read(65537)
        if response.status != 200 or len(raw)>65536:
            raise ValueError("unverified lab response")
        return json.loads(raw)
    finally:
        conn.close()

def context(twin_port, evidence_port, run_id, node_id, *, dynamic_incident=None, include_signals=False, evidence_snapshot=None):
    # Only explicitly named synthetic CI fixtures, never arbitrary tenant data.
    if not re.fullmatch(r"NODE-CI-[A-Z0-9-]{1,80}",node_id):
        raise ValueError("synthetic CI node required")
    if dynamic_incident is None:
        if not re.fullmatch(r"RUN-CI-[A-Z0-9-]{1,80}",run_id):
            raise ValueError("synthetic CI run required")
    elif not (re.fullmatch(r"RUN-[A-F0-9]{16}",run_id) and re.fullmatch(r"INC-CI-INGEST-[a-f0-9]{32}",dynamic_incident)):
        raise ValueError("invalid dynamic binding")
    twin=get(twin_port,"/api/twin/impact/"+node_id)
    evidence=evidence_snapshot if evidence_snapshot is not None else get(evidence_port,"/api/evidence?run_id="+run_id+"&limit=20")
    if twin.get("root")!=node_id or not isinstance(twin.get("affected"),list):
        raise ValueError("invalid impact")
    affected=[]
    for item in twin["affected"]:
        if not re.fullmatch(r"NODE-CI-[A-Z0-9-]{1,80}",item["node_id"]):
            raise ValueError("non-lab topology")
        affected.append({"node_id":item["node_id"],"depth":item["depth"]})
    if not any(x["node_id"]==node_id and x["depth"]==0 for x in affected):
        raise ValueError("missing root")
    verified=[]
    seen={}
    observations=[]
    signals=[]
    items=evidence["items"]
    if not isinstance(items,list) or len(items)>20 or (dynamic_incident is not None and not items):
        raise ValueError("bounded lab evidence required")
    for item in items:
        ref=validated_reference(item)
        provenance=item["provenance"]
        if provenance.get("run_id")!=run_id or provenance.get("synthetic") is not True:
            raise ValueError("non-lab evidence")
        if dynamic_incident is not None:
            payload=item["payload"]
            if (item.get("source")!="v3-synthetic-ingestion" or payload.get("run_id")!=run_id
                or payload.get("incident_id")!=dynamic_incident or payload.get("resource")!=node_id):
                raise ValueError("dynamic evidence binding mismatch")
        digest=hashlib.sha256(json.dumps(item["payload"],sort_keys=True,separators=(",",":")).encode()).hexdigest()
        if digest!=item["payload_hash"]:
            raise ValueError("evidence hash mismatch")
        eid=ref["evidence_id"]
        if eid in seen:
            if dynamic_incident is not None:
                raise ValueError("duplicate dynamic evidence identity")
            if seen[eid]!=item:
                raise ValueError("conflicting evidence identity")
            continue
        seen[eid]=item
        verified.append(ref)
        payload=item["payload"]
        # Dynamic measurements originate in the hashed normalized signal; legacy fixtures use flat payloads.
        if dynamic_incident is not None:
            signal=payload.get("signal")
            if not isinstance(signal,dict):
                raise ValueError("invalid dynamic signal")
            if include_signals:
                signals.append({"evidence_id":item["evidence_id"],"payload_hash":digest,"signal":signal})
            observation=signal.get("observation")
            if observation is not None:
                if (not isinstance(observation,dict) or set(observation)!={"metric","phase","value"}
                    or observation["metric"]!="latency_ms" or not signal.get("source","").startswith("metric:")):
                    raise ValueError("invalid dynamic observation")
                payload=observation
            else:
                payload={}
        if isinstance(payload,dict) and payload.get("metric")=="latency_ms":
            observation={"synthetic":True,"metric":"latency_ms",
                         "phase":payload.get("phase"),"value":payload.get("value"),
                         "evidence_id":item["evidence_id"]}
            if dynamic_incident is not None and "measurement" in signal.get("enterprise",{}):
                from enterprise_context import normalize
                from statistics import median
                scope=normalize(signal["enterprise"],"metric")
                if payload["value"]!=round(median(scope["measurement"]["samples_ms"]),3):
                    raise ValueError("measured median does not match stored samples")
                observation["measurement_scope"]=[node_id,scope["asset_id"],scope.get("application_id")]
                observation["occurred_at"]=scope["occurred_at"]
            observations.append(observation)
    diagnosis=preview(observations)
    # Only the server-read normalized signals are eligible for measured RCA.
    # Preserve the existing UNKNOWN causal state and never authorize an action.
    if dynamic_incident is not None and include_signals and any(
        isinstance(row["signal"].get("enterprise",{}).get("message"),str)
        and row["signal"]["enterprise"]["message"].startswith("HTTP_PROBE_V1 ") for row in signals):
        from measured_rca import assess
        measured=assess(signals,diagnosis)
        diagnosis["candidates"]=measured["candidates"]
        diagnosis["measured_rca"]=measured
    return {"classification":"SYNTHETIC_LAB_CONTEXT","run_id":run_id,"root":node_id,
            "affected":affected,"evidence":verified,"diagnosis":diagnosis,"rca":"UNKNOWN","policy":"DENY",
            "tenant_acl_qualified":False,"production_authorized":False,**({"verified_signals":signals} if include_signals else {})}


def dynamic_context(core_port, token, run_id, twin_port, evidence_port, node_id, *, include_signals=False, multiasset=False):
    """Only a verified DEMO ingestion run mapped to the explicitly configured lab node."""
    from core_read import read_run
    core=read_run(core_port,token,run_id)
    run=core["run"]
    if run["mode"]!="DEMO" or not re.fullmatch(r"INC-CI-INGEST-[a-f0-9]{32}",run["incident_id"]):
        raise ValueError("verified ingestion run required")
    snapshot=None
    if multiasset:
        from enterprise_context import ENTERPRISE_ROOTS, Graph, normalize
        snapshot=get(evidence_port,"/api/evidence?run_id="+run_id+"&limit=20")
        items=snapshot["items"]
        if not 1<=len(items)<=20:
            raise ValueError("bounded evidence required")
        roots={item["payload"].get("resource") for item in items}
        if len(roots)!=1:
            raise ValueError("ambiguous incident root")
        root=next(iter(roots))
        if root!=node_id:
            if root not in ENTERPRISE_ROOTS:
                raise ValueError("unknown enterprise root")
            graph=Graph(get(twin_port,"/api/twin/graph"))
            for item in items:
                sig=item["payload"]["signal"]
                graph.validate_signal(root,normalize(sig["enterprise"],sig["source"].split(":",1)[0]))
            node_id=root
    details=context(twin_port,evidence_port,run_id,node_id,dynamic_incident=run["incident_id"],include_signals=include_signals,evidence_snapshot=snapshot)
    return core,details
