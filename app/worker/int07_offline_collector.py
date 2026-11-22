"""Offline collector seam. No runtime authority or mutation API."""
from copy import deepcopy
from datetime import timedelta
from portal.acme_runtime_context import digest, _utc
from portal.acme_authority_readers import collect_prepared
from portal.acme_authority_continuity import qualify_continuity
from worker.int06a_contract import validate_postcheck, validate_manifest

def collect(expected,intent,readers,observers,policies,registry,clock,expected_sha):
    rows={}
    def capture(k):
        v=deepcopy(readers[k]())
        rows.setdefault(k,[]).append(v)
        return v
    base=collect_prepared(expected,intent,{k:lambda k=k:capture(k) for k in readers},policies,as_of_utc=clock,source_registry={k:registry[k] for k in readers if k in registry})
    def result(b):
        return dict(b,finish_authorized=False,resolution_authorized=False,go=False,runtime_attested=False,live_remediation_authorized=False)
    def refuse(reason,reject=False):
        return result(dict(base,qualification="REJECT" if reject else "BLOCK",reason=reason,context=None,evidence=[]))
    if base["reason"]!="INJECTED_READBACKS_NOT_ATTESTED": return result(base)
    roles=("prepared","receipt","history","postcheck","terminal","terminal_readback","manifest","independent")
    try:
        if set(observers)!=set(roles): return refuse("OBSERVERS_MISSING")
        if set(registry)!=set(readers)|set(roles) or len(set(registry.values()))!=len(registry): return refuse("REGISTRY_INVALID",True)
        now=_utc(clock)
        values={}
        captured={}
        for k in roles:
            source=registry[k]
            if type(policies.get(source)) is not int or policies[source]<0: return refuse("FRESHNESS_POLICY_MISSING:"+k)
            envelope=deepcopy(observers[k]())
            if envelope is None: return refuse("OBSERVATION_MISSING:"+k)
            if envelope["source_id"]!=source or digest(envelope["content"])!=envelope["content_sha256"]: return refuse("OBSERVATION_DIGEST_OR_SOURCE:"+k,True)
            ts=_utc(envelope["observed_at"])
            if ts>now: return refuse("FUTURE:"+k,True)
            if now-ts>timedelta(seconds=policies[source]): return refuse("STALE:"+k)
            if k in ("prepared","history","postcheck","terminal","terminal_readback"):
                observed=_utc(envelope["content"]["observed_at"])
                if observed>ts: return refuse("OBSERVATION_ORDER:"+k,True)
                if now-observed>timedelta(seconds=policies[source]): return refuse("STALE:"+k)
            values[k]=envelope["content"]
            captured[k]=envelope
        second=deepcopy(observers["terminal_readback"]())
        if second is None: return refuse("TERMINAL_READBACK_MISSING")
        if second!=captured["terminal_readback"]: return refuse("TERMINAL_CHANGED",True)
        p,r,h,q,t,a,m,i=(values[k] for k in roles)
        # B owns continuity and receipt predicates; C owns independent capture.
        if a!=i['terminal']: return refuse('TERMINAL_READBACK_MISMATCH',True)
        b=qualify_continuity(expected,intent,{k:v[0] for k,v in rows.items()},policies,as_of_utc=clock,source_registry={k:registry[k] for k in readers},prepared=p,terminal=t,receipt=r,c_manifest=m,independently_read=i,expected_sha=expected_sha,validate_postcheck=validate_postcheck,validate_manifest=validate_manifest,continuity_sources={'history':registry['history'],'postcheck':registry['postcheck'],'terminal':registry['terminal_readback']},history=h,postcheck=q,terminal_readback=second['content'])
        return result(b)
    except (OSError,TimeoutError,ConnectionError): return refuse("OBSERVATION_MISSING")
    except (ValueError,TypeError,KeyError,AttributeError,OverflowError,RecursionError): return refuse("COLLECTOR_INVALID",True)

