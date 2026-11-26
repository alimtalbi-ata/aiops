"""Synthetic latency hypothesis and counterfactual, not causal proof or execution."""
import math
from datetime import datetime

def preview(observations):
    if not isinstance(observations,list) or len(observations)>20:
        raise ValueError("invalid observations")
    samples={}
    metadata={}
    for row in observations:
        if row.get("synthetic") is not True or row.get("metric")!="latency_ms":
            continue
        phase=row.get("phase")
        value=row.get("value")
        eid=row.get("evidence_id")
        if phase not in ("baseline","incident","recovery") or type(value) not in (int,float) or not math.isfinite(value) or value<=0 or not isinstance(eid,str) or not eid:
            raise ValueError("invalid observation")
        if phase in samples:
            raise ValueError("ambiguous sample")
        samples[phase]=(value,eid)
        metadata[phase]=row
    result={"classification":"SYNTHETIC_MODEL_ONLY","root_cause":"UNKNOWN",
            "hypothesis":"UNKNOWN","confidence":None,"evidence_ids":[],
            "preview":None,"operational_decision":"DENY","executed_on_host":False}
    if not {"baseline","incident"}<=set(samples):
        if "recovery" in samples: raise ValueError("recovery requires baseline and incident")
        return result
    baseline,bid=samples["baseline"]
    incident,iid=samples["incident"]
    if bid==iid:
        raise ValueError("distinct evidence required")
    result["evidence_ids"]=[bid,iid]
    if incident>=2*baseline:
        result["hypothesis"]="LATENCY_REGRESSION_OBSERVED"
        result["preview"]={"assumption":"restore measured baseline; not a validated remediation",
                           "observed_ms":incident,"target_ms":baseline,
                           "conditional_reduction_ms":incident-baseline}
    if "recovery" in samples:
        recovery,rid=samples["recovery"]
        scope=metadata["baseline"].get("measurement_scope")
        if (len({bid,iid,rid})!=3 or not isinstance(scope,list) or len(scope)!=3 or not all(isinstance(v,str) and v for v in scope)
            or any(metadata[p].get("measurement_scope")!=scope for p in ("incident","recovery"))):
            raise ValueError("distinct same-scope measured recovery evidence required")
        times=[metadata[p].get("occurred_at") for p in ("baseline","incident","recovery")]
        try:
            parsed=[datetime.strptime(t,"%Y-%m-%dT%H:%M:%SZ") for t in times]
        except (TypeError, ValueError) as exc:
            raise ValueError("recovery measurement chronology invalid") from exc
        if not (all(t==dt.strftime("%Y-%m-%dT%H:%M:%SZ") for t,dt in zip(times,parsed))
                and parsed[0]<parsed[1]<parsed[2]):
            raise ValueError("recovery measurement chronology invalid")
        result["evidence_ids"].append(rid)
        result["recovery"]={"classification":"MEASURED_LAB_RECOVERY_COMPARISON",
                            "baseline_ms":baseline,"incident_ms":incident,"recovery_ms":recovery,
                            "observed_reduction_ms":round(incident-recovery,3),
                            "within_baseline_tolerance":incident>=2*baseline and recovery<=1.5*baseline and recovery<incident,
                            "baseline_tolerance_multiplier":1.5,"causality_established":False,
                            "operational_decision":"DENY","production_authorized":False}
    return result
