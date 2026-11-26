"""Conservative hypotheses from persisted synthetic HTTP probe observations.

A valid hash proves payload integrity, not collector authenticity or causality.
No oracle, scenario label, event ID suffix, free-form instruction or LLM is used.
"""
from datetime import datetime
import json
import math
import re
from enterprise_context import normalize

PREFIX="HTTP_PROBE_V1 "
VERSION="SYNTHETIC_MEASURED_RCA_V1"
FIELDS={"connect_refused","connect_ms","slot_wait_ms","work_ms","http_503"}

def unique_object(pairs):
    result={}
    for key,value in pairs:
        if key in result:
            raise ValueError("duplicate observation field")
        result[key]=value
    return result

def probe(message):
    if not isinstance(message,str) or not message.startswith(PREFIX) or len(message)>256:
        raise ValueError("invalid probe")
    value=json.loads(message[len(PREFIX):],object_pairs_hook=unique_object)
    if not isinstance(value,dict) or set(value)!=FIELDS:
        raise ValueError("unexpected probe fields")
    for key in ("connect_refused","http_503"):
        if type(value[key]) is not int or not 0<=value[key]<=5:
            raise ValueError("invalid count")
    for key in ("connect_ms","slot_wait_ms","work_ms"):
        if type(value[key]) not in (int,float) or not math.isfinite(value[key]) or not 0<=value[key]<=10000:
            raise ValueError("invalid duration")
    return value

def scope(ent):
    return tuple(ent.get(k) for k in ("asset_id","application_id","group_id","user_id"))

def assess(rows,diagnosis):
    """Call only with server-read hash-verified signals from a single lab run."""
    result={"classification":VERSION,"state":"UNKNOWN","candidates":[],
            "causality_established":False,"collector_authenticated":False,
            "confidence":None,"operational_decision":"DENY","production_authorized":False}
    try:
        if not isinstance(rows,list) or not 1<=len(rows)<=20:
            return result
        if diagnosis.get("hypothesis")!="LATENCY_REGRESSION_OBSERVED":
            return result
        measurements={}
        probes={}
        seen=set()
        for row in rows:
            ref={k:row[k] for k in ("evidence_id","payload_hash")}
            if (not re.fullmatch(r"[A-Za-z0-9_.-]{1,128}",ref["evidence_id"])
                or not re.fullmatch(r"[a-f0-9]{64}",ref["payload_hash"])
                or ref["evidence_id"] in seen):
                return result
            seen.add(ref["evidence_id"])
            sig=row["signal"]
            ent=sig.get("enterprise",{})
            source=sig["source"]
            obs=sig.get("observation")
            is_probe=isinstance(ent.get("message"),str) and ent["message"].startswith(PREFIX)
            if obs is None and not is_probe:
                continue
            kind,collector=source.split(":",1)
            if not collector or ":" in collector:
                return result
            ent=normalize(ent,kind)
            stamp=ent["occurred_at"]
            identity=(scope(ent),collector,stamp)
            if is_probe:
                if kind!="log" or identity in probes:
                    return result
                probes[identity]=(probe(ent["message"]),ref)
            else:
                if kind!="metric" or "measurement" not in ent or obs["metric"]!="latency_ms":
                    return result
                phase=obs["phase"]
                if phase not in ("baseline","incident") or phase in measurements:
                    return result
                value=obs["value"]
                if type(value) not in (int,float) or not math.isfinite(value) or value<=0:
                    return result
                from statistics import median
                if value!=round(median(ent["measurement"]["samples_ms"]),3):
                    return result
                measurements[phase]=(identity,value,ref)
        if set(measurements)!={"baseline","incident"} or len(probes)!=2:
            return result
        (bkey,bms,bref),(ikey,ims,iref)=(measurements[p] for p in ("baseline","incident"))
        if bkey[:2]!=ikey[:2] or set(probes)!={bkey,ikey} or not bkey[0][0] or not bkey[0][1]:
            return result
        elapsed=(datetime.strptime(ikey[2],"%Y-%m-%dT%H:%M:%SZ")-datetime.strptime(bkey[2],"%Y-%m-%dT%H:%M:%SZ")).total_seconds()
        if not 0<elapsed<=120 or ims<2*bms:
            return result
        b,blog=probes[bkey]
        a,alog=probes[ikey]
        if b["connect_refused"] or b["http_503"] or b["slot_wait_ms"]>10:
            return result
        delta=ims-bms
        # A substantial measured contribution is required; any competing
        # observation or inconsistent HTTP outcome forces abstention.
        wait=a["slot_wait_ms"]-b["slot_wait_ms"]
        work=a["work_ms"]-b["work_ms"]
        resource=wait>=max(20,.5*delta)
        application=work>=max(20,.5*delta)
        network=a["connect_refused"]>=4 and a["http_503"]==a["connect_refused"]
        if a["connect_refused"]!=a["http_503"] or (a["http_503"] and not network):
            return result
        if sum((resource,application,network))!=1:
            return result
        # Reject secondary substantial changes rather than overfit a single label.
        if network and (wait>=20 or work>=20):
            return result
        if resource and work>=20 or application and wait>=20:
            return result
        family,reason=(("DEPENDENCY_UNAVAILABLE","Repeated connection refusal with matching HTTP failures")
            if network else ("RESOURCE_CONTENTION","Measured wait increase accounts for substantial latency")
            if resource else ("HTTP_DELAY","Measured processing increase accounts for substantial latency"))
        refs=sorted((bref,iref,blog,alog),key=lambda r:r["evidence_id"])
        result.update(state="HYPOTHESIS_SUPPORTED",candidates=[{"family":family,
            "reason":reason,"evidence":refs,"confidence":None,"causality_established":False}])
        return result
    except (ValueError,TypeError,KeyError,AttributeError,OverflowError):
        return result
