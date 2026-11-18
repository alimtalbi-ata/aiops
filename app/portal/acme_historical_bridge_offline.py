"""Offline bridge: never manufacture normalized evidence from Golden projections."""
from copy import deepcopy
from types import SimpleNamespace
from fastapi import HTTPException
from .acme_runtime_context import RECEIPT, digest, _utc
from .acme_int08_phases import admission_v1, result
from .acme_historical_twin_offline import verified_record, check_core_fence
from .acme_historical_policy_offline import qualify

def historical_admission_v1(expected,intent,rows,second_core,registry,policies,*,signed_twin,test_key,as_of_utc):
    """Rows must already be explicit INT08 envelopes; Golden is a supplementary predicate."""
    phase='ADMISSION'
    try:
        expected,intent,rows,second_core,registry,policies,signed_twin=deepcopy(
            (expected,intent,rows,second_core,registry,policies,signed_twin))
        if rows is None or second_core is None or signed_twin is None:
            return result(phase,'HISTORICAL_EVIDENCE_MISSING')
        for row in (rows.get('core'),rows.get('twin'),rows.get('policy'),second_core):
            if row is None:
                return result(phase,'HISTORICAL_EVIDENCE_MISSING')
            content=row['content']['content']
            for field in ('impact_incident_id','snapshot_id','parent_snapshot_id','version'):
                if field not in content:
                    return result(phase,'HISTORICAL_FIELD_MISSING:'+field)
            if (content['snapshot_id']!=expected['snapshot_id'] or content['parent_snapshot_id'] is not None
                or type(content['version']) is not int or content['version']<0):
                return result(phase,'HISTORICAL_SNAPSHOT_INVALID',True)
        base=admission_v1(expected,intent,rows,second_core,registry,policies,as_of_utc=as_of_utc)
        if base['contract_status']!='CONTRACT_ONLY':
            return base
        core=rows['core']['content']['content']
        twin=rows['twin']['content']['content']
        second=second_core['content']['content']
        signed=verified_record(signed_twin,attempt_id=intent['attempt_id'],key=test_key,now=_utc(as_of_utc))
        # Preserve the signed payload verbatim, including nonce and time strings.
        if any(k not in twin or digest(twin[k])!=digest(v) for k,v in signed.items()):
            return result(phase,'HISTORICAL_SIGNED_PAYLOAD_MISMATCH',True)
        reads=iter((core,second))
        check_core_fence(SimpleNamespace(**intent),lambda _:next(reads))
        qualify(intent['attempt_id'],core,signed)
        return base
    except HTTPException:
        return result(phase,'HISTORICAL_PREDICATE_REFUSED',True)
    except (KeyError,TypeError,ValueError,AttributeError,OverflowError,RecursionError):
        return result(phase,'HISTORICAL_INPUT_INVALID',True)
