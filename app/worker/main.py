import os,asyncio,datetime,hashlib,json,logging,uuid
from fastapi import FastAPI,HTTPException,Header
from temporalio import activity
from temporalio.client import Client
from temporalio.worker import Worker
from temporalio.exceptions import WorkflowAlreadyStartedError
from worker.workflow import IncidentWorkflow, STAGES, RETRY
from shared.http import post_json,get_json
from shared.freshness import assess_evidence_freshness
app=FastAPI(title='ACME AioOps Temporal Worker',version='2.1.0')
log=logging.getLogger('aiops2.worker')
worker_state={'polling':False,'last_error':None,'attempts':0}
DENIAL_WORKER_OWNER='worker-'+uuid.uuid4().hex
CORE=os.getenv('CORE_URL','http://aiops2-core:810');EVID=os.getenv('EVIDENCE_URL','http://aiops2-evidence:812');POLICY=os.getenv('POLICY_URL','http://aiops2-policy:813');TWIN=os.getenv('TWIN_URL','http://aiops2-twin:811');ADMIN=os.getenv('AIOPS_INTERNAL_TOKEN') or os.getenv('AIOPS_ADMIN_TOKEN')
if not ADMIN: raise RuntimeError('AIOPS_INTERNAL_TOKEN or AIOPS_ADMIN_TOKEN must be configured')
TEMP=os.getenv('TEMPORAL_ADDRESS','aiops2-temporal:7233');INTEL=os.getenv('INTELLIGENCE_URL','http://aiops2-intelligence:817')
# Bounded by Temporal's 180-second activity deadline, including ledger writes.
# Keep at least 30 seconds for persistence and cancellation overhead.
DGX_HTTP_TIMEOUT_SECONDS=int(os.getenv('AIOPS_DGX_HTTP_TIMEOUT_SECONDS','120'))
if not 15 <= DGX_HTTP_TIMEOUT_SECONDS <= 150:
    raise RuntimeError('AIOPS_DGX_HTTP_TIMEOUT_SECONDS must be between 15 and 150')

def call(method,url,payload): return post_json(url.split('/api/')[0],'/api/'+url.split('/api/',1)[1],payload,timeout=15,token=ADMIN)
def critic_denial_input(mode,analysis,critique,evidence):
    ids=sorted({x['evidence_id'] for x in evidence})
    fresh=assess_evidence_freshness(evidence)
    return {
        'mode':mode, 'command':'EXECUTE',
        'severity':analysis.get('severity','UNKNOWN'),
        'confidence':min(float(analysis.get('confidence',0)),float(critique.get('diagnostic_confidence',0))),
        'evidence_count':len(ids), 'critic_validated':False,
        'redundancy_ok':False, 'evidence_fresh':fresh['status']=='FRESH',
        'preconditions_verified':False, 'fencing_verified':False,'human_approved':False,
    }


def durable_denial_intent(rid,mode,analysis,critique,analysis_id,critique_id,evidence):
    ids=sorted({x['evidence_id'] for x in evidence})
    return post_json(CORE,f'/api/runs/{rid}/denial-intent',{
        'analysis_id':analysis_id,'critique_id':critique_id,
        'evidence_ids':ids,
        'policy_input':critic_denial_input(mode,analysis,critique,evidence),
    },timeout=15,token=ADMIN)


class AtomicDenialBlockError(Exception):
    pass


def reconcile_denial_batch():
    owner=globals().get('DENIAL_WORKER_OWNER')
    if not owner:
        import uuid
        owner='worker-'+uuid.uuid4().hex
    items=post_json(CORE,'/api/denial-intents/claim',{
        'owner':owner,
        'limit':5,
        'lease_seconds':300,
    },timeout=15,token=ADMIN).get('items',[])
    for item in items:
        rid=item['run_id']
        cid=item['critique_id']
        try:
            verdict=post_json(
                POLICY,'/api/policy/check',
                item['policy_input'],timeout=5,token=ADMIN)
            if (verdict.get('state')!='BLOCKED'
                    or verdict.get('decision') not in
                    ('HUMAN_APPROVAL','ESCALATE')):
                raise RuntimeError('unsafe_policy_verdict')
            post_json(
                CORE,
                f'/api/runs/{rid}/denial-intent/{cid}/finalize',
                {
                    'owner':owner,
                    'fencing_token':item['fencing_token'],
                    'verdict':verdict,
                },timeout=15,token=ADMIN)
        except Exception as exc:
            log.warning(
                'critic_denial_reconciliation_pending run=%s critic=%s error=%s',
                rid,cid,type(exc).__name__)


async def reconcile_denial_loop():
    # Independent of Temporal task queue; also recovers after Worker restart.
    while True:
        try:
            await asyncio.to_thread(reconcile_denial_batch)
        except Exception as exc:
            log.warning('critic_denial_reconciliation_scan_failed: %s',type(exc).__name__)
        await asyncio.sleep(10)


def persist_critic_denial(rid, mode, analysis, critique, analysis_id, critique_id, evidence, token):
    """Persist an explicit fail-closed Policy verdict for a rejected Critic.

    This is a terminal denial record, not a transition to the POLICY stage.
    It never approves HITL, remediation or a LIVE effect.
    """
    evidence_ids=sorted({x['evidence_id'] for x in evidence})
    fresh=assess_evidence_freshness(evidence)
    policy_input={
        'mode':mode, 'command':'EXECUTE',
        'severity':analysis.get('severity','UNKNOWN'),
        'confidence':min(float(analysis.get('confidence',0)),float(critique.get('diagnostic_confidence',0))),
        'evidence_count':len(evidence_ids),
        'critic_validated':False,
        'redundancy_ok':False,
        'evidence_fresh':fresh['status']=='FRESH',
        'preconditions_verified':False,
        'fencing_verified':False,
        'human_approved':False,
    }
    verdict=post_json(POLICY,'/api/policy/check',policy_input,timeout=15,token=token)
    if verdict.get('state')!='BLOCKED' or verdict.get('decision') not in ('HUMAN_APPROVAL','ESCALATE'):
        raise RuntimeError('unsafe_policy_response_for_rejected_critic')
    record=post_json(CORE,f'/api/runs/{rid}/policy-record',{
        'policy':verdict,'analysis_id':analysis_id,'critique_id':critique_id,
        'evidence_ids':evidence_ids,'policy_version':'2.1.0',
        'policy_input':policy_input,
    },timeout=15,token=token)
    post_json(CORE,f'/api/runs/{rid}/gates',{
        'stage':'POLICY','state':'BLOCKED','decision':verdict['decision'],
        'reason':verdict.get('reason','critic rejected'),'evidence_ids':evidence_ids,
        'required_evidence':['analyst','critic','observation'],
    },timeout=15,token=token)
    return record['policy_decision_id']


@activity.defn
async def start_run(a):
    # Requests are blocking I/O. Run them off the shared FastAPI/Temporal event loop.
    return await asyncio.to_thread(call,'POST',f'{CORE}/api/runs/{a["run_id"]}/command',{'expected_version':a['version'],'idempotency_key':'START-'+a['run_id'],'command':'START'})

@activity.defn
async def execute_stage(a):
    return await asyncio.to_thread(_execute_stage_blocking,a,activity.info().attempt)

def recover_committed_critic_block(rid):
    detail=get_json(CORE,f'/api/runs/{rid}',token=ADMIN)
    status=detail.get('run',{}).get('status')
    if status!='BLOCKED':
        completed=any(
            e.get('stage')=='DGX_CRITIC'
            and e.get('event_type')=='CRITIC_COMPLETED'
            for e in detail.get('events',[])
        )
        if status!='RUNNING':
            raise AtomicDenialBlockError(
                'critic_replay_invalid_run_state'
            )
        if completed:
            try:
                result=post_json(
                    CORE,
                    f'/api/runs/{rid}/critic-denial-resume',
                    {},
                    timeout=15,
                    token=ADMIN
                )
                if (result.get('run_id')!=rid
                        or result.get('status')!='BLOCKED'
                        or not result.get('denial_hash')):
                    raise ValueError('critic_resume_invalid_response')
                return recover_committed_critic_block(rid)
            except Exception as exc:
                raise AtomicDenialBlockError(
                    'critic_durable_resume_unconfirmed'
                ) from exc
        return None
    receipt=get_json(
        CORE,f'/api/runs/{rid}/critic-denial-block/receipt',
        token=ADMIN
    )
    if (receipt.get('run_id')!=rid
            or receipt.get('status')!='BLOCKED'
            or not receipt.get('denial_hash')
            or not receipt.get('critique_id')
            or not receipt.get('analysis_id')
            or receipt.get('outbox_status') not in ('PENDING','RECONCILED')
            or receipt.get('current_version')!=detail['run'].get('version')
            or not isinstance(receipt.get('version'),int)
            or receipt['version']>receipt['current_version']):
        raise RuntimeError('atomic_denial_receipt_inconsistent')
    return {
        'run_id':rid,
        'stage':'DGX_CRITIC',
        'status':'BLOCKED',
        'version':receipt['version'],
        'policy_denial_recorded':False,
        'denial_intent_durable':True,
        'recovered_from_receipt':True,
    }


def create_hitl_proposal(rid, mode, expected_version):
    """Create a proposal only from a clean, persisted Analyst/Critic pair.

    No natural-language intent is converted into a command. The model must
    provide an allowlisted action type, CI target, evidence, preconditions,
    postconditions and (for high risk) rollback information explicitly.
    """
    detail = get_json(CORE, f'/api/runs/{rid}', token=ADMIN)
    events = detail.get('events', [])
    analyst_event = next((e for e in reversed(events)
        if e.get('stage') == 'DGX_ANALYST'
        and e.get('event_type') == 'ANALYST_COMPLETED'
        and e.get('status') == 'PASS'), None)
    critic_event = next((e for e in reversed(events)
        if e.get('stage') == 'DGX_CRITIC'
        and e.get('event_type') == 'CRITIC_COMPLETED'
        and e.get('status') == 'PASS'), None)
    if not analyst_event or not critic_event:
        return {'status': 'BLOCKED', 'reason': 'validated_analyst_and_critic_events_required'}
    analysis = analyst_event.get('payload', {}).get('analysis', {})
    critique = critic_event.get('payload', {}).get('critique', {})
    if (critique.get('validated') is not True
            or critique.get('issues')
            or critique.get('unsafe_actions')):
        return {'status': 'BLOCKED', 'reason': 'critic_not_cleanly_validated'}
    analysis_id = analyst_event.get('payload', {}).get('analysis_record_id')
    critique_id = critic_event.get('payload', {}).get('critique_record_id')
    if not analysis_id or not critique_id:
        return {'status': 'BLOCKED', 'reason': 'analysis_or_critique_ledger_reference_missing'}
    actions = analysis.get('recommended_actions', [])
    if not isinstance(actions, list):
        return {'status': 'BLOCKED', 'reason': 'analyst_actions_invalid'}
    for action in actions:
        if not isinstance(action, dict):
            continue
        target = action.get('target_ci_id')
        action_type = action.get('action_type')
        risk = action.get('risk_tier')
        preconditions = action.get('preconditions')
        postconditions = action.get('expected_postconditions')
        evidence_ids = sorted(set(action.get('evidence_ids') or []))
        if (action.get('advisory_only') is not True
                or action.get('requires_human_approval') is not True
                or not target or not action_type or not risk
                or not isinstance(preconditions, list) or not preconditions
                or not isinstance(postconditions, list) or not postconditions
                or not evidence_ids):
            continue
        if risk in ('HIGH', 'CRITICAL') and not action.get('rollback_plan'):
            continue
        try:
            proposal = post_json(CORE, f'/api/runs/{rid}/proposals', {
                'source_action_id': action.get('action_id'),
                'analysis_id': analysis_id,
                'critique_id': critique_id,
                'target_ci_id': target,
                'action_type': action_type,
                'risk_tier': risk,
                'parameters': action.get('parameters') or {},
                'evidence_ids': evidence_ids,
                'preconditions': preconditions,
                'expected_postconditions': postconditions,
                'rollback_plan': ({'plan': action.get('rollback_plan')}
                                  if action.get('rollback_plan') else {}),
            }, timeout=15, token=ADMIN)
        except Exception as exc:
            log.warning('HITL proposal rejected by Core validation: %s', type(exc).__name__)
            continue
        return {
            'status': 'WAITING' if mode == 'LIVE' else 'BLOCKED',
            'proposal_id': proposal['proposal_id'],
            'proposal_hash': proposal['proposal_hash'],
            'proposal_revision': proposal['revision'],
            'proposal_status': proposal.get('status', 'PROPOSED'),
            'reason': ('awaiting_human_decision' if mode == 'LIVE'
                       else 'synthetic_proposal_cannot_authorize_live_execution'),
        }
    return {'status': 'BLOCKED', 'reason': 'no_fully_structured_allowlisted_action'}


def _execute_stage_blocking(a,attempt):
    rid,version,stage,mode,scenario=a['run_id'],a['version'],a['stage'],a['mode'],a['scenario_id']
    if stage=='DGX_CRITIC':
        recovered=recover_committed_critic_block(rid)
        if recovered is not None:
            return recovered
    started=call('POST',f'{CORE}/api/runs/{rid}/events',{'expected_version':version,'stage':stage,'event_type':'STAGE_STARTED','event_key':f'{stage}:START','status':'RUNNING','confidence':None,'payload':{'executor':'temporal','retry_stable':True}})
    v=started['version']
    try:
        if stage == 'HITL':
            if mode != 'LIVE':
                # DEMO/REPLAY/STORY are explicitly synthetic. Record that the
                # approval gate is not exercised; never mint a synthetic
                # approval or let a synthetic identity authorize remediation.
                payload = {
                    'reason': 'synthetic_mode_no_live_approval',
                    'synthetic': True,
                    'approval_required': False,
                    'execution_allowed': False,
                }
                event = call('POST', f'{CORE}/api/runs/{rid}/events', {
                    'expected_version': v,
                    'stage': stage,
                    'event_type': 'HITL_SIMULATION_SKIPPED',
                    'event_key': f'{stage}:SIMULATION-SKIPPED',
                    'status': 'PASS',
                    'decision': 'SIMULATE',
                    'confidence': 0,
                    'payload': payload,
                })
                post_json(CORE, f'/api/runs/{rid}/checkpoint',
                          {'stage': stage, 'version': event['version']}, token=ADMIN)
                return {
                    'run_id': rid, 'stage': stage, 'status': 'PASS',
                    'version': event['version'], **payload,
                }

            result = create_hitl_proposal(rid, mode, v)
            proposal_id = result.get('proposal_id')
            payload = {
                'reason': result.get('reason'),
                'proposal_id': proposal_id,
                'proposal_hash': result.get('proposal_hash'),
                'proposal_revision': result.get('proposal_revision'),
                'proposal_status': result.get('proposal_status'),
                'synthetic': False,
                'execution_allowed': False,
            }
            event = call('POST', f'{CORE}/api/runs/{rid}/events', {
                'expected_version': v,
                'stage': stage,
                'event_type': 'HITL_PROPOSAL_CREATED' if proposal_id else 'HITL_PROPOSAL_BLOCKED',
                'event_key': f'{stage}:PROPOSAL',
                'status': 'RUNNING' if result.get('status') == 'WAITING' else 'BLOCKED',
                'decision': 'HUMAN_APPROVAL',
                'confidence': 0,
                'payload': payload,
            })
            post_json(CORE, f'/api/runs/{rid}/checkpoint',
                      {'stage': stage, 'version': event['version']}, token=ADMIN)
            if result.get('status') != 'WAITING':
                blocked = call('POST', f'{CORE}/api/runs/{rid}/command', {
                    'expected_version': event['version'],
                    'idempotency_key': f'HITL-BLOCK-{rid}',
                    'command': 'BLOCK',
                })
                return {
                    'run_id': rid, 'stage': stage, 'status': 'BLOCKED',
                    'version': blocked['version'], **payload,
                }
            return {
                'run_id': rid, 'stage': stage, 'status': 'WAITING',
                'version': event['version'],
                'proposal_id': proposal_id,
                'proposal_hash': result['proposal_hash'],
                'proposal_revision': result['proposal_revision'],
                'hitl_required': True,
                'execution_allowed': False,
            }

        # This baseline has no qualified LIVE evidence/CMDB/RAG/analyst/critic/remediation adapters.
        # Never manufacture evidence or confidence values for a LIVE run.
        if mode == 'LIVE':
            blocked = call('POST',f'{CORE}/api/runs/{rid}/events',{
                'expected_version':v,
                'stage':stage,
                'event_type':'LIVE_ADAPTER_UNAVAILABLE',
                'event_key':f'{stage}:LIVE-ADAPTER-UNAVAILABLE',
                'status':'BLOCKED',
                'decision':'HUMAN_APPROVAL',
                'confidence':0.0,
                'payload':{
                    'reason':'LIVE execution is disabled until real evidence adapters and policy/HITL qualification are implemented',
                    'synthetic_evidence_created':False,
                    'stage_adapter_qualified':False,
                },
            })
            state = call('POST',f'{CORE}/api/runs/{rid}/command',{
                'expected_version':blocked['version'],
                'idempotency_key':f'LIVE-BLOCK-{rid}',
                'command':'BLOCK',
            })
            return {'run_id':rid,'stage':stage,'status':'BLOCKED','version':state['version'],'sequence':blocked['sequence']}
        synthetic=True
        if synthetic and stage=='OBSERVE':
            post_json(TWIN,'/api/twin/synthetic-event',{'action':'SET_STATE','target_node_id':'ACME-SAN-FABRIC-A','run_id':rid,'payload':{'state':'DEGRADED','health':0.42}},token=ADMIN)
            post_json(TWIN,'/api/twin/synthetic-event',{'action':'OBSERVE','target_node_id':'ACME-SAN-FABRIC-A','run_id':rid,'payload':{'metric':'fc_errors','value':184,'unit':'errors/min','status':'CRITICAL'}},token=ADMIN)
            # STAGE_STARTED is an immutable, idempotent event. Reuse its actual
            # recorded timestamp so Temporal retry cannot create a conflicting
            # observation with the same source/external identity.
            timeline=get_json(CORE,f'/api/runs/{rid}',token=ADMIN)
            stable_event=next((e for e in timeline.get('events',[])
                               if e.get('sequence')==started['sequence']
                               and e.get('stage')=='OBSERVE'
                               and e.get('event_type')=='STAGE_STARTED'),None)
            if not stable_event or not stable_event.get('occurred_at'):
                raise RuntimeError('stable_observation_timestamp_unavailable')
            observed=stable_event['occurred_at']
            post_json(EVID,'/api/evidence',{'source':'twin-simulator','external_id':f'{rid}:fc-errors','observed_at':observed,'claim':'Synthetic ACME scenario reports FC errors at 184 errors/min on ACME-SAN-FABRIC-A.','confidence':0.95,'provenance':{'synthetic':True,'run_id':rid,'stage':'OBSERVE','adapter':'twin-simulator','scenario_id':scenario,'observed_at':observed},'payload':{'node_id':'ACME-SAN-FABRIC-A','metric':'fc_errors','value':184,'unit':'errors/min','status':'CRITICAL','mode':mode,'run_id':rid}},token=ADMIN)
            post_json(EVID,'/api/evidence',{'source':'twin-simulator','external_id':f'{rid}:fabric-health','observed_at':observed,'claim':'Synthetic ACME scenario reports ACME-SAN-FABRIC-A degraded with health 0.42.','confidence':0.95,'provenance':{'synthetic':True,'run_id':rid,'stage':'OBSERVE','adapter':'twin-simulator','scenario_id':scenario,'observed_at':observed},'payload':{'node_id':'ACME-SAN-FABRIC-A','state':'DEGRADED','health':0.42,'mode':mode,'run_id':rid}},token=ADMIN)
            # DEMO B adds independent-looking *synthetic* observation types; all
            # provenance stays explicitly synthetic and remains open to Critic.
            run_detail=get_json(CORE,f'/api/runs/{rid}',token=ADMIN)
            incident_id=str(run_detail.get('run',{}).get('incident_id',''))
            if incident_id.startswith('INC-DEMO-ENRICHED-'):
                enriched=[
                    ('multipath', 'Synthetic RHEL multipath snapshot: 3/4 active paths, one degraded; path ownership unverified.',
                     {'node_id':'ACME-SRV-RHEL01','active_paths':3,'total_paths':4,'failed_paths':1}),
                    ('fabric-b', 'Synthetic redundant fabric B reports healthy, not an independently acquired measurement.',
                     {'node_id':'ACME-SAN-FABRIC-B','state':'HEALTHY','health':0.98}),
                    ('payment-latency', 'Synthetic payment service latency rose from 90ms baseline to 340ms p95.',
                     {'node_id':'ACME-SVC-PAYMENTS','metric':'p95_latency_ms','value':340,'baseline':90}),
                    ('payment-errors', 'Synthetic payment gateway reports 1.8% errors, baseline 0.1%; correlation not proven.',
                     {'node_id':'ACME-SVC-PAYMENTS','metric':'error_rate_percent','value':1.8,'baseline':0.1}),
                ]
                for suffix,claim,payload in enriched:
                    post_json(EVID,'/api/evidence',{
                        'source':'acme-enriched-simulator',
                        'external_id':f'{rid}:{suffix}',
                        'observed_at':observed,
                        'claim':claim,
                        'confidence':0.75,
                        'provenance':{'synthetic':True,'run_id':rid,'stage':'OBSERVE',
                            'adapter':'acme-enriched-simulator','scenario_id':scenario,
                            'observed_at':observed},
                        'payload':{**payload,'mode':mode,'run_id':rid,'synthetic':True}
                    },token=ADMIN)
        if stage in ('DGX_ANALYST','DGX_CRITIC'):
            try:
                detail=get_json(CORE,f'/api/runs/{rid}',token=ADMIN)
                ledger=get_json(EVID,f'/api/evidence?run_id={rid}',token=ADMIN).get('items',[])
                source_evidence=[x for x in ledger if x.get('source')!='run:'+rid+':'+stage.lower() and not str(x.get('source','')).startswith('run:'+rid+':')]
                scenario_context=get_json(CORE,f'/api/scenarios/{scenario}',token=ADMIN)
                incident={'incident_id':detail['run'].get('incident_id'),'run_id':rid,'title':scenario_context.get('scenario',{}).get('name',scenario),'severity':'UNKNOWN','source':'synthetic-scenario','synthetic':mode!='LIVE'}
                if stage=='DGX_ANALYST':
                    response=post_json(INTEL,'/api/intelligence/analyze',{'incident':incident,'evidence':source_evidence,'mode':mode,'context':{'scenario':scenario_context}},timeout=DGX_HTTP_TIMEOUT_SECONDS,token=ADMIN)
                    result=response['analysis']
                    evidence_ids=sorted(x['evidence_id'] for x in source_evidence)
                    evidence_key=hashlib.sha256(json.dumps(evidence_ids,separators=(',',':')).encode()).hexdigest()[:16]
                    record=post_json(CORE,f'/api/runs/{rid}/analysis-record',{'analysis':result,'evidence_ids':evidence_ids,'idempotency_key':f'ANALYST-{rid}-V2-{evidence_key}','provider':response.get('provider','openai-compatible'),'model':response.get('model','unknown'),'prompt_version':response.get('prompt_version','analyst-v2.0')},timeout=15,token=ADMIN)
                    saved=call('POST',f'{CORE}/api/runs/{rid}/events',{'expected_version':v,'stage':stage,'event_type':'ANALYST_COMPLETED','event_key':f'{stage}:COMPLETE','status':'PASS','evidence_ids':evidence_ids,'confidence':result['confidence'],'payload':{'analysis':result,'analysis_record_id':record['analysis_id'],'provider':response.get('provider','openai-compatible'),'model':response.get('model','unknown'),'prompt_version':response.get('prompt_version','analyst-v2.0'),'synthetic':mode!='LIVE','evidence_count':len(source_evidence)}})
                    post_json(CORE,f'/api/runs/{rid}/checkpoint',{'stage':stage,'version':saved['version']},token=ADMIN)
                    return saved
                analyst_event=next((e for e in reversed(detail.get('events',[])) if e.get('stage')=='DGX_ANALYST' and e.get('event_type')=='ANALYST_COMPLETED'),None)
                if not analyst_event or not isinstance(analyst_event.get('payload',{}).get('analysis'),dict):
                    raise RuntimeError('analyst_result_missing')
                response=post_json(INTEL,'/api/intelligence/critic',{'incident':incident,'evidence':source_evidence,'mode':mode,'context':{'scenario':scenario_context},'analyst':analyst_event['payload']['analysis']},timeout=DGX_HTTP_TIMEOUT_SECONDS,token=ADMIN)
                result=response['critique'];state='PASS' if result.get('validated') is True else 'BLOCKED'
                analysis_record_id=analyst_event.get('payload',{}).get('analysis_record_id')
                if not analysis_record_id: raise RuntimeError('analysis_ledger_record_missing')
                evidence_ids=sorted(x['evidence_id'] for x in source_evidence)
                evidence_key=hashlib.sha256(json.dumps(evidence_ids,separators=(',',':')).encode()).hexdigest()[:16]
                critique_record=post_json(CORE,f'/api/runs/{rid}/critique-record',{'critique':result,'analysis_id':analysis_record_id,'evidence_ids':evidence_ids,'idempotency_key':f'CRITIC-{rid}-{analysis_record_id}-{evidence_key}','provider':response.get('provider','openai-compatible'),'model':response.get('model','unknown')},timeout=15,token=ADMIN)
                denial_snapshot=critic_denial_input(
                    mode,analyst_event['payload']['analysis'],
                    result,source_evidence
                ) if state=='BLOCKED' else None
                saved=call('POST',f'{CORE}/api/runs/{rid}/events',{'expected_version':v,'stage':stage,'event_type':'CRITIC_COMPLETED','event_key':f'{stage}:COMPLETE','status':state,'evidence_ids':evidence_ids,'decision':result.get('final_recommendation'),'confidence':result.get('diagnostic_confidence',0),'payload':{'critique':result,'analysis_record_id':analysis_record_id,'critique_record_id':critique_record['critique_id'],'denial_policy_input':denial_snapshot,'provider':response.get('provider','openai-compatible'),'model':response.get('model','unknown'),'synthetic':mode!='LIVE','evidence_count':len(source_evidence)}})
                post_json(CORE,f'/api/runs/{rid}/checkpoint',{'stage':stage,'version':saved['version']},token=ADMIN)
                if state=='BLOCKED':
                    try:
                        block=post_json(
                            CORE,
                            f'/api/runs/{rid}/critic-denial-resume',
                            {},
                            timeout=15,
                            token=ADMIN
                        )
                        if (block.get('run_id')!=rid
                                or block.get('status')!='BLOCKED'
                                or not block.get('denial_hash')):
                            raise ValueError('critic_resume_invalid_response')
                    except Exception as exc:
                        raise AtomicDenialBlockError(
                            'atomic_denial_block_unconfirmed'
                        ) from exc
                    return {
                        'run_id':rid,'stage':stage,'status':'BLOCKED',
                        'version':block['version'],
                        'policy_denial_recorded':False,
                        'denial_intent_durable':True,
                    }
                return saved
            except AtomicDenialBlockError:
                raise
            except Exception as exc:
                blocked_event=call('POST',f'{CORE}/api/runs/{rid}/events',{'expected_version':v,'stage':stage,'event_type':'INTELLIGENCE_UNAVAILABLE','event_key':f'{stage}:UNAVAILABLE','status':'BLOCKED','decision':'HUMAN_APPROVAL','confidence':0,'payload':{'reason':type(exc).__name__,'synthetic_evidence_created':False,'execution_allowed':False}})
                blocked=call('POST',f'{CORE}/api/runs/{rid}/command',{'expected_version':blocked_event['version'],'idempotency_key':f'INTELLIGENCE-BLOCK-{rid}-{stage}','command':'BLOCK'})
                return {'run_id':rid,'stage':stage,'status':'BLOCKED','version':blocked['version']}
        ev=post_json(EVID,'/api/evidence',{'source':f'run:{rid}:{stage.lower()}','claim':f'{stage} completed for scenario {scenario}','confidence':0.94,'provenance':{'synthetic':synthetic,'run_id':rid,'stage':stage,'scenario_id':scenario,'record_type':'stage_marker'},'payload':{'stage':stage,'scenario_id':scenario,'mode':mode,'attempt':attempt}},token=ADMIN)
        eids=[ev['evidence_id']]
        if stage=='POLICY':
            detail=get_json(CORE,f'/api/runs/{rid}',token=ADMIN)
            analyst_event=next((e for e in reversed(detail.get('events',[])) if e.get('stage')=='DGX_ANALYST' and e.get('event_type')=='ANALYST_COMPLETED'),None)
            critic_event=next((e for e in reversed(detail.get('events',[])) if e.get('stage')=='DGX_CRITIC' and e.get('event_type')=='CRITIC_COMPLETED'),None)
            analysis=(analyst_event or {}).get('payload',{}).get('analysis',{})
            critique=(critic_event or {}).get('payload',{}).get('critique',{})
            source_ledger=get_json(EVID,f'/api/evidence?run_id={rid}',token=ADMIN).get('items',[])
            source_evidence=[x for x in source_ledger if str(x.get('source','')).startswith('twin-simulator') or not str(x.get('source','')).startswith('run:'+rid+':')]
            analysis_record_id=(analyst_event or {}).get('payload',{}).get('analysis_record_id')
            critique_record_id=(critic_event or {}).get('payload',{}).get('critique_record_id')
            freshness=assess_evidence_freshness(source_evidence)
            policy_input={'mode':mode,'command':'EXECUTE','severity':analysis.get('severity','UNKNOWN'),'confidence':min(float(analysis.get('confidence',0)),float(critique.get('diagnostic_confidence',0))),'evidence_count':len(source_evidence),'critic_validated':critique.get('validated') is True,'redundancy_ok':False if not source_evidence else True,'evidence_fresh':freshness['status']=='FRESH','evidence_freshness':freshness,'preconditions_verified':False,'fencing_verified':False,'human_approved':False}
            pol=post_json(POLICY,'/api/policy/check',policy_input,token=ADMIN)
            decision_record=post_json(CORE,f'/api/runs/{rid}/policy-record',{'policy':pol,'analysis_id':analysis_record_id,'critique_id':critique_record_id,'evidence_ids':[x['evidence_id'] for x in source_evidence],'policy_version':'2.1.0','policy_input':policy_input},timeout=15,token=ADMIN)
            pol['policy_decision_id']=decision_record['policy_decision_id']
            post_json(CORE,f'/api/runs/{rid}/gates',{'stage':'POLICY','state':pol['state'],'decision':pol['decision'],'reason':pol['reason'],'evidence_ids':[x['evidence_id'] for x in source_evidence],'required_evidence':['analyst','critic','twin','observation']},token=ADMIN)
            if pol['state']!='PASS':
                blocked_event=call('POST',f'{CORE}/api/runs/{rid}/events',{'expected_version':v,'stage':stage,'event_type':'GATE_BLOCKED','event_key':f'{stage}:BLOCKED','status':'BLOCKED','evidence_ids':eids,'decision':pol['decision'],'confidence':.94,'payload':pol})
                blocked=call('POST',f'{CORE}/api/runs/{rid}/command',{'expected_version':blocked_event['version'],'idempotency_key':f'POLICY-BLOCK-{rid}','command':'BLOCK'})
                return {'run_id':rid,'stage':stage,'status':'BLOCKED','version':blocked['version']}
        completed=call('POST',f'{CORE}/api/runs/{rid}/events',{'expected_version':v,'stage':stage,'event_type':'STAGE_COMPLETED','event_key':f'{stage}:COMPLETE','status':'PASS','evidence_ids':eids,'confidence':.94,'payload':{'executor':'temporal','synthetic':synthetic,'attempt':attempt}})
        post_json(CORE,f'/api/runs/{rid}/checkpoint',{'stage':stage,'version':completed['version']},token=ADMIN)
        if synthetic:
            post_json(CORE,f'/api/runs/{rid}/demo-artifacts',{'artifact_type':'stage','title':stage,'sequence_no':completed['sequence'],'caption':f'{stage} — {mode} — evidence linked','payload':{'scenario_id':scenario,'synthetic':True}},token=ADMIN)
        return completed
    except Exception as exc:
        try: call('POST',f'{CORE}/api/runs/{rid}/events',{'expected_version':v,'stage':stage,'event_type':'STAGE_FAILED','event_key':f'{stage}:FAIL','status':'FAIL','confidence':0,'payload':{'error':str(exc)[:500],'attempt':attempt}})
        finally: raise
@activity.defn
async def finish_run(a):
    return await asyncio.to_thread(call,'POST',f'{CORE}/api/runs/{a["run_id"]}/command',{'expected_version':a['version'],'idempotency_key':'RESOLVE-'+a['run_id'],'command':'RESOLVE'})
@app.get('/health')
def health():
 if not worker_state['polling']:
  raise HTTPException(503,{'status':'unavailable','component':'worker','reason':'temporal_poller_not_running'})
 return {'status':'ok','component':'worker','executor':'temporal','task_queue':'aiops-runner'}
@app.get('/metrics')
def metrics(): return 'aiops_worker_up 1\n'
@app.post('/api/execution/start')
async def start(args:dict,authorization:str|None=Header(default=None)):
 if (authorization or '').removeprefix('Bearer ')!=ADMIN:raise HTTPException(401,'invalid internal token')
 c=await Client.connect(TEMP)
 try:
  h=await c.start_workflow(IncidentWorkflow.run,args,id=args['run_id'],task_queue='aiops-runner');return {'workflow_id':h.id,'run_id':args['run_id'],'executor':'temporal'}
 except WorkflowAlreadyStartedError:
  return {'workflow_id':args['run_id'],'run_id':args['run_id'],'executor':'temporal','idempotent':True}
async def worker_main():
 while True:
  worker_state['polling']=False
  worker_state['attempts']+=1
  try:
   c=await Client.connect(TEMP)
   async with Worker(c,task_queue='aiops-runner',workflows=[IncidentWorkflow],activities=[execute_stage,start_run,finish_run]):
    worker_state['polling']=True
    worker_state['last_error']=None
    await asyncio.Event().wait()
  except Exception as exc:
   worker_state['polling']=False
   worker_state['last_error']=type(exc).__name__
   log.exception('Temporal polling worker unavailable; retrying in 5s')
   await asyncio.sleep(5)
async def reconcile_hitl_decisions_loop():
 """At-least-once Core-to-Temporal decision delivery.

 Core proposal status is authoritative. Repeated identical Temporal signals are
 idempotent; a workflow rejects conflicting payloads. This poller is a delivery
 bridge, not an execution authorization mechanism.
 """
 client=None
 while True:
  try:
   if client is None:
    client=await Client.connect(TEMP)
   snapshot=get_json(CORE,'/api/proposals?status=ALL&limit=200',token=ADMIN)
   items=snapshot.get('items',[]) if isinstance(snapshot,dict) else []
   for item in items:
    status=item.get('status')
    if status not in ('APPROVED','REJECTED','REVOKED'):
     continue
    rid=item.get('run_id')
    pid=item.get('proposal_id')
    digest=item.get('proposal_hash')
    revision=item.get('revision')
    if not all(isinstance(v,str) and v for v in (rid,pid,digest)) or type(revision) is not int:
     continue
    decision='APPROVE' if status=='APPROVED' else 'REJECT'
    payload={
     'proposal_id':pid,
     'proposal_hash':digest,
     'proposal_revision':revision,
     'decision':decision,
     'source_status':status,
    }
    try:
     handle=client.get_workflow_handle(rid)
     await handle.signal(IncidentWorkflow.submit_hitl_decision,payload)
    except Exception as exc:
     log.debug('HITL signal delivery deferred: %s',type(exc).__name__)
  except Exception as exc:
   client=None
   log.warning('HITL decision reconciliation unavailable: %s',type(exc).__name__)
  await asyncio.sleep(5)


@app.on_event('startup')
async def startup():
 asyncio.create_task(worker_main())
 asyncio.create_task(reconcile_denial_loop())
 asyncio.create_task(reconcile_hitl_decisions_loop())
