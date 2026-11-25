"""Synthetic latency hypothesis and counterfactual, not causal proof or execution."""
import math

def preview(observations):
    if not isinstance(observations,list) or len(observations)>20:
        raise ValueError("invalid observations")
    samples={}
    for row in observations:
        if row.get("synthetic") is not True or row.get("metric")!="latency_ms":
            continue
        phase=row.get("phase")
        value=row.get("value")
        eid=row.get("evidence_id")
        if phase not in ("baseline","incident") or type(value) not in (int,float) or not math.isfinite(value) or value<=0 or not isinstance(eid,str) or not eid:
            raise ValueError("invalid observation")
        if phase in samples:
            raise ValueError("ambiguous sample")
        samples[phase]=(value,eid)
    result={"classification":"SYNTHETIC_MODEL_ONLY","root_cause":"UNKNOWN",
            "hypothesis":"UNKNOWN","confidence":None,"evidence_ids":[],
            "preview":None,"operational_decision":"DENY","executed_on_host":False}
    if set(samples)!={"baseline","incident"}:
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
    return result
