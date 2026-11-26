"""Conservative admission for measured synthetic incidents; no causal or action claim."""
from datetime import datetime,timezone
from ingestion_demo import ingest
from enterprise_context import normalize,ENTERPRISE_ROOTS,digest

VERSION="SYNTHETIC_MEASURED_INCIDENT_ADMISSION_V1"

def admit(records,graph,*,now=None):
    if not isinstance(records,list) or not 1<=len(records)<=20:
        raise ValueError("bounded batch required")
    normalized=ingest(records)
    incidents=normalized["incidents"]
    if len(incidents)!=1:
        raise ValueError("single resource required")
    incident=incidents[0]
    root=incident["resource"]
    if root not in ENTERPRISE_ROOTS:
        raise ValueError("unverified resource")
    graph.scope(root)
    signals=incident["evidence"]
    refs=[{"event_id":s["event_id"],"sha256":s["sha256"]} for s in signals]
    result={"classification":VERSION,"batch_sha256":digest(incident),
            "resource":root,"references":refs,"received":len(records),"unique":len(signals),
            "disposition":"INSUFFICIENT_EVIDENCE","admitted":False,
            "root_cause":"UNKNOWN","causality_established":False,
            "operational_decision":"DENY","production_authorized":False}
    scopes=set()
    phases={}
    times=[]
    now=now or datetime.now(timezone.utc)
    if now.tzinfo is None: raise ValueError("timezone required")
    for signal in signals:
        kind=signal["source"].split(":",1)[0]
        if "enterprise" not in signal:
            return result
        ent=normalize(signal["enterprise"],kind)
        graph.validate_signal(root,ent)
        scopes.add(tuple(ent.get(k) for k in ("asset_id","application_id","group_id","user_id")))
        stamp=datetime.strptime(ent["occurred_at"],"%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        times.append(stamp)
        obs=signal.get("observation")
        if obs is None:
            continue
        if "measurement" not in ent or obs["phase"] not in ("baseline","incident"):
            result["disposition"]="AMBIGUOUS_EVIDENCE"
            return result
        phase=obs["phase"]
        if phase in phases:
            result["disposition"]="AMBIGUOUS_EVIDENCE"
            return result
        phases[phase]=(obs["value"],stamp)
    if len(scopes)!=1:
        result["disposition"]="AMBIGUOUS_EVIDENCE"
        return result
    if any((now-t).total_seconds() < -5 or (now-t).total_seconds()>120 for t in times):
        result["disposition"]="STALE_OR_FUTURE_EVIDENCE"
        return result
    if set(phases)!={"baseline","incident"}:
        return result
    baseline,before=phases["baseline"]
    incident,after=phases["incident"]
    if not before<after or (after-before).total_seconds()>120:
        result["disposition"]="AMBIGUOUS_EVIDENCE"
        return result
    result["measurements"]={"baseline_ms":baseline,"incident_ms":incident}
    if incident<2*baseline:
        result["disposition"]="NOMINAL_OBSERVATION"
        return result
    if not any(s["source"].startswith(("log:","event:")) for s in signals):
        return result
    result["disposition"]="MEASURED_INCIDENT_CANDIDATE"
    result["admitted"]=True
    return result
