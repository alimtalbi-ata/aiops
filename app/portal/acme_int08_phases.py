"""Additive offline phase contracts. No scheduling, FINISH or runtime admission."""
from copy import deepcopy
from datetime import timedelta
from hashlib import sha256
from .acme_runtime_context import digest, _utc, _id, RECEIPT
from .acme_authority_readers import collect_prepared
from worker.acme_simulated_hitl import validate_readbacks, verify_no_effect_receipt, SandboxDenied
from worker.int06a_contract import validate_postcheck

SCHEMA='aiops.int08.phase.v1'
ROLES=('core','twin','policy','critic','hitl')

def result(phase, reason, reject=False, nominal=False, projection=None):
    return dict(schema=SCHEMA,phase=phase,qualification='REJECT' if reject else 'BLOCK',
        contract_status='CONTRACT_ONLY' if nominal else 'UNQUALIFIED',reason=reason,
        binding_status='UNBOUND',runtime_freshness='UNKNOWN',runtime_attested=False,
        live_remediation_authorized=False,execution_allowed=False,finish_authorized=False,
        resolution_authorized=False,projection=projection)

def _require(ok, reason):
    if not ok: raise ValueError(reason)

def _observe(role,row,identity,snapshot,registry,policies,now):
    if row is None: raise LookupError('MISSING:'+role)
    _require(type(row) is dict and set(row)=={'role','source_id','classification','identity','snapshot_id','observed_at','content','content_sha256'},'ENVELOPE_SHAPE')
    _require(row['role']==role and row['source_id']==registry[role],'SOURCE_MISMATCH')
    _require(row['classification']=='STORY_OFFLINE','UNATTESTED_RUNTIME_CLAIM')
    _require(row['identity']==identity and row['snapshot_id']==snapshot,'IDENTITY_OR_SNAPSHOT')
    _require(type(row['content']) is dict and digest(row['content'])==row['content_sha256'],'DIGEST_MISMATCH')
    observed=_utc(row['observed_at'])
    _require(observed<=now,'FUTURE_OBSERVATION')
    limit=policies.get(registry[role])
    if type(limit) is not int or limit<0: raise LookupError('FRESHNESS_POLICY_MISSING:'+role)
    if now-observed>timedelta(seconds=limit): raise LookupError('STALE:'+role)
    return row['content']

def _registry(registry,roles):
    _require(type(registry) is dict and set(registry)==set(roles) and
             all(_id(v) for v in registry.values()) and len(set(registry.values()))==len(roles),'REGISTRY_INVALID')

def _projection(identity,rows):
    return dict(identity={k:identity[k] for k in RECEIPT},impact_incident_id=identity['impact_incident_id'],
        provenance=[dict(role=k,source_id=v['source_id'],observed_at=v['observed_at'],
                         content_sha256=v['content_sha256'],classification='STORY_OFFLINE',
                         runtime_freshness='UNKNOWN') for k,v in rows.items()],
        binding_status='UNBOUND',runtime_freshness='UNKNOWN',runtime_attested=False)

def admission_v1(expected,intent,rows,second_core,registry,policies,*,as_of_utc):
    """INT08 phase envelopes carry exact normalized V4 rows for core/twin/policy."""
    phase='ADMISSION'
    try:
        expected,intent,rows,second_core,registry,policies=deepcopy((expected,intent,rows,second_core,registry,policies))
        _registry(registry,ROLES)
        if rows is None or second_core is None: raise LookupError('ADMISSION_MISSING')
        _require(set(rows)==set(ROLES),'ADMISSION_ROLES')
        identity={k:intent[k] for k in RECEIPT}
        identity['impact_incident_id']=expected['impact_incident_id']
        now=_utc(as_of_utc); snapshot=expected['snapshot_id']
        values={k:_observe(k,rows[k],identity,snapshot,registry,policies,now) for k in ROLES}
        second=_observe('core',second_core,identity,snapshot,registry,policies,now)
        _require(second_core==rows['core'],'CORE_CHANGED')
        v4={k:values[k] for k in ('core','twin','policy')}
        for k,v in v4.items():
            _require(v['source_id']==registry[k] and v['observed_at']==rows[k]['observed_at'],'V4_PROVENANCE_MISMATCH')
        core_reads=iter((v4['core'],second))
        base=collect_prepared(expected,intent,{'core':lambda:next(core_reads),'twin':lambda:v4['twin'],'policy':lambda:v4['policy']},policies,as_of_utc=as_of_utc,source_registry={k:registry[k] for k in v4})
        if base['reason']!='INJECTED_READBACKS_NOT_ATTESTED':
            return result(phase,base['reason'],base['qualification']=='REJECT')
        c,t,p=(v4[k]['content'] for k in ('core','twin','policy'))
        validate_readbacks(intent,core=c,twin=t,policy=p,now=now)
        _require(_utc(t['issued_at'])<=now,'FUTURE_APPROVAL')
        _require(values['critic']=={'decision':'ALLOW','core_sha256':digest(v4['core']),'twin_sha256':digest(v4['twin'])},'CRITIC_UNQUALIFIED')
        _require(values['hitl']=={'kind':'SIMULATED','human_approved':False,'execution_allowed':False,'effect_allowed':False,'twin_sha256':digest(v4['twin']),'policy_sha256':digest(v4['policy'])},'HITL_UNQUALIFIED')
        _require(t['approval_nonce'].isascii() and bool(t['approval_nonce']),'NONCE_INVALID')
        return result(phase,'ADMISSION_CONSISTENT_NOT_ATTESTED',nominal=True,projection=_projection(identity,rows))
    except LookupError as e:
        return result(phase,str(e))
    except (ValueError,TypeError,AttributeError,OverflowError,RecursionError,SandboxDenied) as e:
        return result(phase,'ADMISSION_INVALID:'+str(e),True)

def preterminal_v1(expected,intent,admission_rows,second_core,admission_registry,rows,registry,policies,*,as_of_utc):
    """Revalidate admission evidence, never trust a supplied prior verdict."""
    phase='PRETERMINAL'
    try:
        expected,intent,admission_rows,second_core,admission_registry,rows,registry,policies=deepcopy((expected,intent,admission_rows,second_core,admission_registry,rows,registry,policies))
        base=admission_v1(expected,intent,admission_rows,second_core,admission_registry,policies,as_of_utc=as_of_utc)
        if base['contract_status']!='CONTRACT_ONLY':
            return result(phase,base['reason'],base['qualification']=='REJECT')
        roles=('receipt','history_prefix','postcheck')
        _registry(registry,roles)
        _require(not set(registry.values()) & set(admission_registry.values()),'SOURCE_COLLISION')
        if rows is None: raise LookupError('PRETERMINAL_MISSING')
        _require(set(rows)==set(roles),'PRETERMINAL_ROLES')
        identity={k:intent[k] for k in RECEIPT}; seven=dict(identity)
        identity['impact_incident_id']=expected['impact_incident_id']
        now=_utc(as_of_utc)
        receipt,history,post=(_observe(k,rows[k],identity,expected['snapshot_id'],registry,policies,now) for k in roles)
        _require(verify_no_effect_receipt(receipt,seven) and type(receipt['effect_receipts']) is int,'RECEIPT_INVALID')
        core=admission_rows['core']['content']['content']; twin=admission_rows['twin']['content']['content']
        _require(receipt['core_request_sha256']==core['request_sha256'] and receipt['core_source_event_ids']==core['source_event_ids'] and receipt['twin_approval_nonce_sha256']==sha256(twin['approval_nonce'].encode('ascii')).hexdigest(),'RECEIPT_PREPARED_MISMATCH')
        _require(history=={'phase':'PREFIX','receipt_sha256':receipt['receipt_sha256'],'admission_sha256':digest(admission_rows)},'HISTORY_PREFIX_MISMATCH')
        _require(set(post)=={'history_prefix_sha256','identity','critic_decision','twin_state','policy_decision','hitl_valid','external_effect_count','postcheck_verified'} and post['history_prefix_sha256']==digest(history),'POSTCHECK_LINK_MISMATCH')
        validate_postcheck(intent=intent,independently_read=post)
        times=[max(_utc(v['observed_at']) for v in admission_rows.values())]+[_utc(rows[k]['observed_at']) for k in roles]
        _require(all(a<b for a,b in zip(times,times[1:])),'PHASE_TIME_ORDER')
        return result(phase,'PRETERMINAL_CONSISTENT_NOT_ATTESTED',nominal=True,projection=_projection(identity,{**admission_rows,**rows}))
    except LookupError as e:
        return result(phase,str(e))
    except (ValueError,TypeError,AttributeError,OverflowError,RecursionError,SandboxDenied) as e:
        return result(phase,'PRETERMINAL_INVALID:'+str(e),True)
