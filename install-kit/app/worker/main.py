from worker.fs_lab_activity import fs_lab_inspect
from fastapi.responses import PlainTextResponse

class PrometheusTextResponse(PlainTextResponse):
    media_type = "text/plain; version=0.0.4"

import os,asyncio,datetime,hashlib,json,logging,uuid
from fastapi import FastAPI,HTTPException,Header
from temporalio import activity
from temporalio.client import Client
from temporalio.worker import Worker
from temporalio.exceptions import WorkflowAlreadyStartedError
from worker.workflow import IncidentWorkflow, ReviewEvidenceWorkflow, STAGES, RETRY
from shared.http import post_json,get_json
from shared.freshness import assess_evidence_freshness
app=FastAPI(title='ACME AioOps Temporal Worker',version='2.1.0')
log=logging.getLogger('aiops2.worker')
worker_state={'polling':False,'last_error':None,'attempts':0}
DENIAL_WORKER_OWNER='worker-'+uuid.uuid4().hex
CORE=os.getenv('CORE_URL','http://aiops2-core:810');PORTAL=os.getenv('PORTAL_URL','http://aiops2-portal:777');EVID=os.getenv('EVIDENCE_URL','http://aiops2-evidence:812');POLICY=os.getenv('POLICY_URL','http://aiops2-policy:813');TWIN=os.getenv('TWIN_URL','http://aiops2-twin:811');ADMIN=os.getenv('AIOPS_INTERNAL_TOKEN') or os.getenv('AIOPS_ADMIN_TOKEN')
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


def _maybe_create_synthetic_hitl_proposal(rid, mode, scenario, analysis_event,
                                                critique_record, critique, evidence_scope):
    """Create a proposal only from an actual validated Analyst action and Critic record."""
    if mode == "LIVE" or not scenario.startswith("SCN-ACME-TEST-HITL-"):
        return None
    analysis = analysis_event.get("payload", {}).get("analysis", {})
    analysis_id = analysis_event.get("payload", {}).get("analysis_record_id")
    critique_id = critique_record.get("critique_id")
    if not isinstance(analysis, dict) or not analysis_id or not critique_id:
        return None
    if critique.get("validated") is not True or critique.get("issues") or critique.get("unsafe_actions"):
        return None
    action_types = {
        "CI-COLLECT-READONLY": "COLLECT_DIAGNOSTICS",
        "COLLECT_DIAGNOSTICS": "COLLECT_DIAGNOSTICS",
    }
    for action in analysis.get("recommended_actions", []):
        if not isinstance(action, dict):
            continue
        source_id = action.get("action_id")
        action_type = action_types.get(source_id)
        risk = action.get("risk_tier")
        target = action.get("target_ci_id")
        evidence_ids = sorted(set(action.get("evidence_ids") or []))
        if (not action_type or action.get("advisory_only") is not True
                or action.get("requires_human_approval") is not True
                or risk != "LOW" or not target or not evidence_ids
                or not set(evidence_ids).issubset(set(analysis_event.get("evidence_ids") or []))
                or not set(evidence_ids).issubset(set(evidence_scope or []))):
            continue
        payload = {
            "analysis_id": analysis_id,
            "critique_id": critique_id,
            "source_action_id": source_id,
            "target_ci_id": target,
            "action_type": action_type,
            "risk_tier": risk,
            "parameters": {"mode": "READ_ONLY", "intent": action.get("intent", "")},
            "evidence_ids": evidence_ids,
            "preconditions": action.get("preconditions") or [],
            "expected_postconditions": [
                action.get("expected_effect", ""),
                *(action.get("verification_steps") or []),
            ],
            "rollback_plan": {"description": action.get("rollback_plan", "No side effects; none required.")},
        }
        if not payload["preconditions"] or not all(payload["expected_postconditions"]):
            continue
        try:
            proposal = post_json(
                CORE, f"/api/runs/{rid}/proposals", payload,
                timeout=15, token=ADMIN
            )
        except Exception as exc:
            log.warning("HITL proposal creation failed for %s: %s", rid, type(exc).__name__)
            return None
        if (isinstance(proposal, dict) and proposal.get("proposal_id")
                and proposal.get("proposal_hash") and proposal.get("status") == "PROPOSED"
                and proposal.get("execution_allowed") is False):
            return proposal
    return None


def _sync_glpi_run_best_effort(run_id, stage, timeout=20):
    """Publish a current Core snapshot without changing the Temporal result."""
    last_error = None
    try:
        return post_json(
            PORTAL, f"/api/internal/glpi/runs/{run_id}/sync",
            {"stage": str(stage)}, timeout=timeout, token=ADMIN
        )
    except Exception as exc:
        last_error = type(exc).__name__
    log.warning("GLPI report sync failed for %s at %s: %s", run_id, stage, last_error)
    return {"status": "SYNC_FAILED", "run_id": run_id,
            "sync_stage": str(stage), "reason": last_error}


@activity.defn
async def start_run(a):
    # Requests are blocking I/O. Run them off the shared FastAPI/Temporal event loop.
    result = await asyncio.to_thread(
        call, 'POST', f'{CORE}/api/runs/{a["run_id"]}/command',
        {'expected_version':a['version'],'idempotency_key':'START-'+a['run_id'],'command':'START'}
    )
    return result


@activity.defn
async def execute_stage(a):
    result = await asyncio.to_thread(_execute_stage_blocking, a, activity.info().attempt)
    if a["stage"] in {"NORMALIZE", "OBSERVE", "DGX_ANALYST", "DGX_CRITIC", "POLICY", "HITL", "VERIFY"} or result.get("status") == "BLOCKED":
        await asyncio.to_thread(_sync_glpi_run_best_effort, a["run_id"], a["stage"])
    return result

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
    hitl_event = next((
        event for event in reversed(detail.get('events', []))
        if event.get('event_type') == 'HITL_PROPOSAL_CREATED'
        and isinstance(event.get('payload'), dict)
    ), None)
    if hitl_event:
        return {
            'run_id': rid, 'stage': 'HITL', 'status': 'BLOCKED',
            'version': detail['run'].get('version'),
            'hitl_proposal_id': hitl_event['payload'].get('proposal_id'),
            'execution_allowed': False, 'recovered_from_event': True,
        }
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



def policy_command_for_mode(mode):
    # Existing simulation contract: observe in synthetic modes; LIVE stays strict.
    if not isinstance(mode, str) or mode not in ('DEMO', 'REPLAY', 'STORY', 'LIVE'):
        raise ValueError('unknown execution mode')
    return 'EXECUTE' if mode == 'LIVE' else 'OBSERVE'


def _demo_simulation_authorized(detail, rid, scenario, version, mode):
    # Local admission only: never a human approval or a LIVE authorization.
    if mode != 'DEMO' or not isinstance(detail, dict) or type(version) is not int:
        return False
    run = detail.get('run')
    if not isinstance(run, dict) or any(run.get(k) != value for k, value in (
            ('run_id', rid), ('scenario_id', scenario), ('mode', 'DEMO'),
            ('status', 'RUNNING'), ('version', version))):
        return False
    if type(run.get('version')) is not int:
        return False
    gates = detail.get('gates')
    if not isinstance(gates, list):
        return False
    policy = [g for g in gates if isinstance(g, dict) and g.get('stage') == 'POLICY']
    if len(policy) != 1:
        return False
    gate = policy[0]
    evidence = gate.get('evidence_ids')
    return (gate.get('state') == 'PASS' and gate.get('decision') == 'SIMULATE'
            and isinstance(evidence, list) and bool(evidence)
            and all(isinstance(eid, str) and eid.strip() for eid in evidence))



def _canonical_intelligence_incident(detail, rid, mode):
    run = detail.get('run', {})
    iid = run.get('incident_id')
    if run.get('run_id') != rid or run.get('mode') != mode or not iid:
        raise ValueError('intelligence_run_identity_mismatch')
    registry = get_json(CORE, '/api/incidents?limit=500', token=ADMIN)
    rows = registry.get('items') if isinstance(registry, dict) else None
    if not isinstance(rows, list):
        raise ValueError('incident_registry_invalid')
    matches = [row for row in rows if isinstance(row, dict)
               and row.get('incident_id') == iid]
    if len(matches) != 1:
        raise ValueError('canonical_incident_missing_or_ambiguous')
    incident = matches[0]
    if (not isinstance(incident.get('title'), str) or not incident['title'].strip()
            or not isinstance(incident.get('severity'), str)
            or not incident['severity'].strip()
            or type(incident.get('synthetic')) is not bool
            or not isinstance(incident.get('source'), str)
            or not incident['source'].strip()):
        raise ValueError('canonical_incident_invalid')
    if mode != 'LIVE' and incident['synthetic'] is not True:
        raise ValueError('synthetic_mode_incident_mismatch')
    return {**{key: incident[key] for key in
               ('incident_id', 'title', 'severity', 'source', 'synthetic')},
            'run_id': rid}

def _execute_stage_blocking(a,attempt):
    rid,version,stage,mode,scenario=a['run_id'],a['version'],a['stage'],a['mode'],a['scenario_id']
    policy_command = policy_command_for_mode(mode)
    if stage=='DGX_CRITIC':
        recovered=recover_committed_critic_block(rid)
        if recovered is not None:
            return recovered
    started=call('POST',f'{CORE}/api/runs/{rid}/events',{'expected_version':version,'stage':stage,'event_type':'STAGE_STARTED','event_key':f'{stage}:START','status':'RUNNING','confidence':None,'payload':{'executor':'temporal','retry_stable':True}})
    v=started['version']
    try:
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
        # AIOPS2_FS_REAL_EVIDENCE_V30
        fs_scenarios = (
            'SCN-FS-REAL-FULL',
            'SCN-FS-INSUFFICIENT-DATA',
        )
        if scenario in fs_scenarios and stage == 'OBSERVE':
            fs = a.get('fs_evidence')
            if not isinstance(fs, dict):
                raise ValueError('fs_evidence_missing')
            if fs.get('run_id') != rid:
                raise ValueError('fs_evidence_run_mismatch')
            if fs.get('source') != 'REAL_FS_LAB':
                raise ValueError('fs_evidence_source_invalid')
            if fs.get('filesystem') != '/fs-lab':
                raise ValueError('fs_evidence_target_invalid')
            if fs.get('synthetic_measurement') is not False:
                raise ValueError('fs_measurement_not_real')
            usage = fs.get('used_percent')
            if type(usage) is not int or not 0 <= usage <= 100:
                raise ValueError('fs_usage_invalid')
            observations = fs.get('observations')
            if not isinstance(observations, dict):
                raise ValueError('fs_observations_invalid')
            output = observations.get('df_du_ls')
            if not isinstance(output, str) or not output or len(output) > 12000:
                raise ValueError('fs_observation_output_invalid')

            timeline = get_json(CORE, f'/api/runs/{rid}', token=ADMIN)
            stable_event = next((
                e for e in timeline.get('events', [])
                if e.get('sequence') == started['sequence']
                and e.get('stage') == 'OBSERVE'
                and e.get('event_type') == 'STAGE_STARTED'
            ), None)
            if not stable_event or not stable_event.get('occurred_at'):
                raise RuntimeError('fs_observation_timestamp_unavailable')

            observed = stable_event['occurred_at']
            evidence = post_json(EVID, '/api/evidence', {
                'source': 'real-fs-lab',
                'external_id': f'{rid}:fs-lab-observation',
                'observed_at': observed,
                'claim': (
                    f'Real isolated filesystem /fs-lab measured at '
                    f'{usage}% usage; threshold 90%.'
                ),
                'confidence': 1.0,
                'provenance': {
                    'synthetic': False,
                    'run_id': rid,
                    'stage': 'OBSERVE',
                    'adapter': 'fs-lab-inspect',
                    'scenario_id': scenario,
                    'observed_at': observed,
                },
                'payload': {
                    'run_id': rid,
                    'filesystem': '/fs-lab',
                    'target_ci_id': 'CI-FS-LAB-12M',
                    'used_percent': usage,
                    'threshold_percent': 90,
                    'alert_firing': usage >= 90,
                    'command_output': output,
                    'mode': mode,
                    'synthetic': False,
                },
            }, token=ADMIN)

            twin_observation = post_json(
                TWIN,
                '/api/twin/observations',
                {'evidence_id': evidence['evidence_id']},
                token=ADMIN,
            )
            if (
                twin_observation.get('status') != 'PASS'
                or twin_observation.get('evidence_id') != evidence['evidence_id']
                or twin_observation.get('synthetic') is not False
            ):
                raise RuntimeError('fs_twin_observation_invalid')

            completed = call('POST', f'{CORE}/api/runs/{rid}/events', {
                'expected_version': v,
                'stage': stage,
                'event_type': 'STAGE_COMPLETED',
                'event_key': f'{stage}:COMPLETE',
                'status': 'PASS',
                'evidence_ids': [evidence['evidence_id']],
                'confidence': 1.0,
                'payload': {
                    'executor': 'temporal',
                    'synthetic': False,
                    'filesystem': '/fs-lab',
                    'used_percent': usage,
                    'alert_firing': usage >= 90,
                },
            })
            post_json(
                CORE,
                f'/api/runs/{rid}/checkpoint',
                {'stage': stage, 'version': completed['version']},
                token=ADMIN,
            )
            return completed

        if synthetic and stage=='OBSERVE' and scenario not in fs_scenarios:
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
                scenario_extra = []
                if scenario == 'SCN-ACME-TEST-HITL-CHANGE':
                    scenario_extra = [
                        ('change-window', 'Synthetic change calendar: maintenance window is not confirmed; approval state UNKNOWN.',
                         {'node_id':'ACME-APP-PORTAL','change_window':'UNKNOWN','change_approved':False}),
                    ]
                elif scenario == 'SCN-ACME-TEST-HITL-STORAGE':
                    scenario_extra = [
                        ('storage-path-ownership', 'Synthetic storage snapshot: one degraded path has no verified owner-to-target mapping.',
                         {'node_id':'ACME-SRV-RHEL01','path_mapping_verified':False,'degraded_paths':1}),
                    ]
                elif scenario == 'SCN-ACME-TEST-HITL-CRITICAL':
                    scenario_extra = [
                        ('payment-impact', 'Synthetic business impact: 78% of payment attempts are reported affected; impact requires human validation.',
                         {'node_id':'ACME-SVC-PAYMENTS','affected_transactions_percent':78,'severity':'P1'}),
                    ]
                elif scenario == 'SCN-ACME-TEST-BLOCK-EVIDENCE':
                    scenario_extra = [
                        ('contradictory-fc-errors', 'Synthetic monitoring source reports 0 FC errors/min, conflicting with the Twin observation of 184 errors/min.',
                         {'node_id':'ACME-SAN-FABRIC-A','metric':'fc_errors','value':0,'unit':'errors/min','status':'HEALTHY'}),
                    ]
                for suffix, claim, payload in scenario_extra:
                    post_json(EVID, '/api/evidence', {
                        'source': 'acme-scenario-fixture',
                        'external_id': f'{rid}:{suffix}',
                        'observed_at': observed,
                        'claim': claim,
                        'confidence': 0.65,
                        'provenance': {
                            'synthetic': True, 'run_id': rid, 'stage': 'OBSERVE',
                            'adapter': 'acme-scenario-fixture', 'scenario_id': scenario,
                            'observed_at': observed,
                        },
                        'payload': {**payload, 'mode': mode, 'run_id': rid, 'synthetic': True},
                    }, token=ADMIN)
        if stage in ('DGX_ANALYST','DGX_CRITIC'):
            try:
                detail=get_json(CORE,f'/api/runs/{rid}',token=ADMIN)
                ledger=get_json(EVID,f'/api/evidence?run_id={rid}',token=ADMIN).get('items',[])
                source_evidence=[x for x in ledger if x.get('source')!='run:'+rid+':'+stage.lower() and not str(x.get('source','')).startswith('run:'+rid+':')]
                scenario_context=get_json(CORE,f'/api/scenarios/{scenario}',token=ADMIN)
                incident = (_canonical_intelligence_incident(detail, rid, mode)
                            if scenario not in fs_scenarios else {})
                # AIOPS2_FS_INTELLIGENCE_CONTEXT_V30
                if scenario in fs_scenarios:
                    real_fs_evidence = [
                        item for item in source_evidence
                        if item.get('source') == 'real-fs-lab'
                        and item.get('provenance', {}).get('synthetic') is False
                        and item.get('provenance', {}).get('run_id') == rid
                    ]
                    if not real_fs_evidence:
                        raise RuntimeError('real_fs_evidence_missing')

                    source_evidence = real_fs_evidence
                    latest = real_fs_evidence[-1]
                    measurement = latest.get('payload', {})
                    used = measurement.get('used_percent')
                    if type(used) is not int or not 0 <= used <= 100:
                        raise RuntimeError('real_fs_usage_invalid')

                    incident = {
                        'incident_id': detail['run'].get('incident_id'),
                        'run_id': rid,
                        'title': 'Isolated filesystem /fs-lab capacity incident',
                        'severity': 'HIGH' if used >= 90 else 'UNKNOWN',
                        'source': 'real-fs-lab',
                        'synthetic': False,
                        'filesystem': '/fs-lab',
                        'used_percent': used,
                        'threshold_percent': 90,
                    }
                    scenario_context = {
                        'scenario': {
                            'scenario_id': scenario,
                            'name': 'Real isolated filesystem investigation',
                        },
                        'filesystem': '/fs-lab',
                        'measurement_source': 'real-fs-lab',
                        'used_percent': used,
                        'evidence_ids': [
                            item['evidence_id'] for item in real_fs_evidence
                        ],
                        'insufficient_data_case': (
                            scenario == 'SCN-FS-INSUFFICIENT-DATA'
                        ),
                    }

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
                if state == 'PASS':
                    proposal = _maybe_create_synthetic_hitl_proposal(
                        rid, mode, scenario, analyst_event, critique_record, result, evidence_ids
                    )
                    if proposal:
                        hitl_event = call('POST', f'{CORE}/api/runs/{rid}/events', {
                            'expected_version': saved['version'],
                            'stage': 'HITL',
                            'event_type': 'HITL_PROPOSAL_CREATED',
                            'event_key': 'HITL:PROPOSAL:' + proposal['proposal_id'],
                            'status': 'BLOCKED',
                            'decision': 'HUMAN_APPROVAL',
                            'evidence_ids': evidence_ids,
                            'confidence': result.get('diagnostic_confidence', 0),
                            'payload': {
                                'proposal_id': proposal['proposal_id'],
                                'proposal_hash': proposal['proposal_hash'],
                                'proposal_status': proposal['status'],
                                'execution_allowed': False,
                            },
                        })
                        blocked = call('POST', f'{CORE}/api/runs/{rid}/command', {
                            'expected_version': hitl_event['version'],
                            'idempotency_key': 'HITL-BLOCK-' + rid,
                            'command': 'BLOCK',
                        })
                        return {
                            'run_id': rid, 'stage': 'HITL', 'status': 'BLOCKED',
                            'version': blocked['version'],
                            'hitl_proposal_id': proposal['proposal_id'],
                            'execution_allowed': False,
                        }
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
        # AIOPS2_FS_STAGE_MARKERS_V30
        if scenario in fs_scenarios:
            # AIOPS2_FS_SENSITIVE_STAGES_GUARD_V30
            if stage in {'POLICY', 'HITL', 'REMEDIATE', 'VERIFY', 'RECONCILE', 'LEARN'}:
                blocked_event = call('POST', f'{CORE}/api/runs/{rid}/events', {
                    'expected_version': v,
                    'stage': stage,
                    'event_type': 'FS_STAGE_NOT_QUALIFIED',
                    'event_key': f'{stage}:FS-NOT-QUALIFIED',
                    'status': 'BLOCKED',
                    'decision': 'HUMAN_APPROVAL',
                    'confidence': 0.0,
                    'payload': {
                        'reason': 'FS HITL and restricted remediation executor not yet integrated',
                        'execution_allowed': False,
                        'synthetic_evidence_created': False,
                    },
                })
                state = call('POST', f'{CORE}/api/runs/{rid}/command', {
                    'expected_version': blocked_event['version'],
                    'idempotency_key': f'FS-SAFETY-BLOCK-{rid}-{stage}',
                    'command': 'BLOCK',
                })
                return {
                    'run_id': rid,
                    'stage': stage,
                    'status': 'BLOCKED',
                    'version': state['version'],
                    'execution_allowed': False,
                }
            completed = call('POST', f'{CORE}/api/runs/{rid}/events', {
                'expected_version': v,
                'stage': stage,
                'event_type': 'STAGE_COMPLETED',
                'event_key': f'{stage}:COMPLETE',
                'status': 'PASS',
                'confidence': None,
                'payload': {
                    'executor': 'temporal',
                    'record_type': 'stage_progress',
                    'field_measurement': False,
                },
            })
            post_json(
                CORE,
                f'/api/runs/{rid}/checkpoint',
                {'stage': stage, 'version': completed['version']},
                token=ADMIN,
            )
            return completed

        # Non-FS synthetic stages require current, exact-Run Policy admission.
        # The existing FS guard above has already returned; it is never relaxed.
        if stage in ('HITL', 'REMEDIATE', 'VERIFY'):
            detail = get_json(CORE, f'/api/runs/{rid}', token=ADMIN)
            if not _demo_simulation_authorized(detail, rid, scenario, v, mode):
                denied = call('POST', f'{CORE}/api/runs/{rid}/events', {
                    'expected_version': v, 'stage': stage,
                    'event_type': 'DEMO_POLICY_GATE_NOT_AUTHORIZED',
                    'event_key': f'{stage}:DEMO-NOT-AUTHORIZED',
                    'status': 'BLOCKED', 'decision': 'HUMAN_APPROVAL',
                    'confidence': 0.0,
                    'payload': {'execution_allowed': False,
                                'synthetic_evidence_created': False,
                                'reason': 'Current run-bound PASS/SIMULATE Policy gate required'},
                })
                state = call('POST', f'{CORE}/api/runs/{rid}/command', {
                    'expected_version': denied['version'],
                    'idempotency_key': f'DEMO-SAFETY-BLOCK-{rid}-{stage}',
                    'command': 'BLOCK',
                })
                return {'run_id': rid, 'stage': stage, 'status': 'BLOCKED',
                        'version': state['version'], 'execution_allowed': False}

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
            policy_input={'mode':mode,'command':policy_command,'severity':analysis.get('severity','UNKNOWN'),'confidence':min(float(analysis.get('confidence',0)),float(critique.get('diagnostic_confidence',0))),'evidence_count':len(source_evidence),'critic_validated':critique.get('validated') is True,'redundancy_ok':False if not source_evidence else True,'evidence_fresh':freshness['status']=='FRESH','evidence_freshness':freshness,'preconditions_verified':False,'fencing_verified':False,'human_approved':False}
            pol=post_json(POLICY,'/api/policy/check',policy_input,token=ADMIN)
            decision_record=post_json(CORE,f'/api/runs/{rid}/policy-record',{'policy':pol,'analysis_id':analysis_record_id,'critique_id':critique_record_id,'evidence_ids':[x['evidence_id'] for x in source_evidence],'policy_version':'2.1.0','policy_input':policy_input},timeout=15,token=ADMIN)
            pol['policy_decision_id']=decision_record['policy_decision_id']
            post_json(CORE,f'/api/runs/{rid}/gates',{'stage':'POLICY','state':pol['state'],'decision':pol['decision'],'reason':pol['reason'],'evidence_ids':[x['evidence_id'] for x in source_evidence],'required_evidence':['analyst','critic','twin','observation']},token=ADMIN)
            if pol['state']!='PASS':
                blocked_event=call('POST',f'{CORE}/api/runs/{rid}/events',{'expected_version':v,'stage':stage,'event_type':'GATE_BLOCKED','event_key':f'{stage}:BLOCKED','status':'BLOCKED','evidence_ids':eids,'decision':pol['decision'],'confidence':.94,'payload':pol})
                blocked=call('POST',f'{CORE}/api/runs/{rid}/command',{'expected_version':blocked_event['version'],'idempotency_key':f'POLICY-BLOCK-{rid}','command':'BLOCK'})
                return {'run_id':rid,'stage':stage,'status':'BLOCKED','version':blocked['version']}
        completed=call('POST',f'{CORE}/api/runs/{rid}/events',{'expected_version':v,'stage':stage,'event_type':'STAGE_COMPLETED','event_key':f'{stage}:COMPLETE','status':'PASS','evidence_ids':eids,'confidence':.94,'payload':{'executor':'temporal','synthetic':synthetic,'attempt':attempt,'execution_allowed':False,'human_approval_verified':False}})
        post_json(CORE,f'/api/runs/{rid}/checkpoint',{'stage':stage,'version':completed['version']},token=ADMIN)
        if synthetic:
            post_json(CORE,f'/api/runs/{rid}/demo-artifacts',{'artifact_type':'stage','title':stage,'sequence_no':completed['sequence'],'caption':f'{stage} — {mode} — evidence linked','payload':{'scenario_id':scenario,'synthetic':True}},token=ADMIN)
        return completed
    except Exception as exc:
        try: call('POST',f'{CORE}/api/runs/{rid}/events',{'expected_version':v,'stage':stage,'event_type':'STAGE_FAILED','event_key':f'{stage}:FAIL','status':'FAIL','confidence':0,'payload':{'error':str(exc)[:500],'attempt':attempt}})
        finally: raise
@activity.defn
async def finish_run(a):
    result = await asyncio.to_thread(
        call, 'POST', f'{CORE}/api/runs/{a["run_id"]}/command',
        {'expected_version':a['version'],'idempotency_key':'RESOLVE-'+a['run_id'],'command':'RESOLVE'}
    )
    await asyncio.to_thread(_sync_glpi_run_best_effort, a["run_id"], "FINAL", 8)
    return result
@app.get('/health')
def health():
 if not worker_state['polling']:
  raise HTTPException(503,{'status':'unavailable','component':'worker','reason':'temporal_poller_not_running'})
 return {'status':'ok','component':'worker','executor':'temporal','task_queue':'aiops-runner'}
# FS52_REAL_FILESYSTEM_METRICS
@app.get('/metrics', response_class=PrometheusTextResponse)
def metrics():
    import http.client
    import socket
    from pathlib import Path

    lines = ['aiops_worker_up 1']

    socket_path = os.environ.get('AIOPS_FS_BRIDGE_UNIX_SOCKET', '')
    token_file = os.environ.get('AIOPS_FS_BRIDGE_TOKEN_FILE', '')

    if not socket_path and not token_file:
        return '\n'.join(lines) + '\n'

    if not socket_path or not token_file:
        raise HTTPException(503, 'fs_metrics_bridge_incomplete')

    token = Path(token_file).read_text(encoding='utf-8').strip()
    if len(token) < 32:
        raise HTTPException(503, 'fs_metrics_bridge_token_invalid')

    class UnixConnection(http.client.HTTPConnection):
        def connect(self):
            self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self.sock.settimeout(self.timeout)
            self.sock.connect(socket_path)

    connection = UnixConnection('localhost', timeout=10)
    try:
        connection.request(
            'POST', '/execute',
            body=json.dumps({'action': 'inspect'}),
            headers={
                'Authorization': 'Bearer ' + token,
                'Content-Type': 'application/json',
            },
        )
        response = connection.getresponse()
        payload = json.loads(response.read())
        if response.status != 200 or payload.get('status') != 'SUCCESS':
            raise RuntimeError('fs_inspection_failed')
    except Exception as exc:
        raise HTTPException(503, 'fs_metrics_inspection_unavailable') from exc
    finally:
        connection.close()

    from worker.fs_lab_evidence import build_fs_evidence

    evidence = build_fs_evidence(
        'RUN-FS-METRICS',
        {
            'run_id': 'RUN-FS-METRICS',
            'source': 'REAL_FS_LAB',
            'filesystem': '/fs-lab',
            'inspection': payload,
            'read_only': True,
        },
    )

    used = evidence['used_percent']
    firing = 1 if evidence['alert_firing'] else 0
    labels = '{filesystem="/fs-lab",ci="CI-FS-LAB-12M"}'

    lines.append('aiops2_fs_lab_used_percent' + labels + ' ' + str(used))
    lines.append('aiops2_fs_lab_alert_firing' + labels + ' ' + str(firing))
    return '\n'.join(lines) + '\n'
@app.post('/api/execution/start')
async def start(args:dict,authorization:str|None=Header(default=None)):
 if (authorization or '').removeprefix('Bearer ')!=ADMIN:raise HTTPException(401,'invalid internal token')
 try: policy_command_for_mode(args.get('mode'))
 except ValueError: raise HTTPException(422, 'invalid execution mode')
 # Defense in depth: Core's CREATED/WAITING eligibility must also be
 # enforced at the Worker ingress, including direct internal callers.
 rid = args.get('run_id')
 if not isinstance(rid, str) or not rid:
  raise HTTPException(422, 'run_id required')
 try:
  detail = await asyncio.to_thread(get_json, CORE, f'/api/runs/{rid}', token=ADMIN)
 except Exception as exc:
  from requests.exceptions import HTTPError
  if isinstance(exc, HTTPError) and getattr(exc.response, 'status_code', None) == 404:
   # A missing run is not a Core outage; never reach Temporal.
   raise HTTPException(404, 'run not found') from exc
  raise HTTPException(503, 'run state verification unavailable') from exc
 run = detail.get('run') if isinstance(detail, dict) else None
 status = run.get('status') if isinstance(run, dict) else None
 if status not in ('CREATED', 'WAITING'):
  raise HTTPException(409, f'run not executable from {status or "UNKNOWN"}')
 if (run.get('run_id') != rid or run.get('mode') != args.get('mode')
         or run.get('scenario_id') != args.get('scenario_id')
         or type(args.get('version')) is not int
         or type(run.get('version')) is not int
         or run.get('version') != args.get('version')):
  raise HTTPException(409, 'execution request does not match current Core run')
 c=await Client.connect(TEMP)
 try:
  h=await c.start_workflow(IncidentWorkflow.run,args,id=args['run_id'],task_queue='aiops-runner');return {'workflow_id':h.id,'run_id':args['run_id'],'executor':'temporal'}
 except WorkflowAlreadyStartedError:
  return {'workflow_id':args['run_id'],'run_id':args['run_id'],'executor':'temporal','idempotent':True}

@activity.defn(name='demo_evidence_phase')
async def demo_evidence_phase(args:dict)->dict:
    def execute():
        import urllib.request
        phase=args['phase'];job_id=args['job_id']
        import re
        if not re.fullmatch(r'ENRICH-DRV-[A-F0-9]{24}',job_id) or phase not in ('COLLECT','ANALYZE','CRITIC','POLICY','PUBLISH','FAIL'):
            raise ValueError('invalid enrichment activity scope')
        timeout={'COLLECT':70,'ANALYZE':170,'CRITIC':170,'POLICY':45,'PUBLISH':260,'FAIL':25}[phase]
        request=urllib.request.Request(CORE.rstrip('/')+'/api/internal/demo-enrichments/'+job_id+'/'+phase,
            data=b'{}',method='POST',headers={'Authorization':'Bearer '+ADMIN,'Content-Type':'application/json'})
        with urllib.request.urlopen(request,timeout=timeout) as response:return json.load(response)
    return await asyncio.to_thread(execute)

@app.post('/api/demo-enrichment/execute')
async def execute_demo_enrichment(args:dict,authorization:str|None=Header(default=None)):
    import hmac,re
    if not hmac.compare_digest((authorization or '').removeprefix('Bearer '),ADMIN):raise HTTPException(401,'invalid internal token')
    job_id=args.get('job_id')
    if set(args)!={'job_id'} or not isinstance(job_id,str) or not re.fullmatch(r'ENRICH-DRV-[A-F0-9]{24}',job_id):raise HTTPException(422,'invalid enrichment job')
    descriptor=await asyncio.to_thread(get_json,CORE,'/api/internal/demo-enrichments/'+job_id+'/descriptor',token=ADMIN)
    if (descriptor.get('job_id')!=job_id or descriptor.get('workflow_id')!=job_id or descriptor.get('mode')!='DEMO'
        or descriptor.get('synthetic') is not True or descriptor.get('execution_allowed') is not False):raise HTTPException(409,'unqualified enrichment descriptor')
    from temporalio.common import WorkflowIDReusePolicy
    client=await Client.connect(TEMP)
    try:
        handle=await client.start_workflow(ReviewEvidenceWorkflow.run,{'job_id':job_id},id=job_id,task_queue='aiops-runner',id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE)
        return {'job_id':job_id,'workflow_id':handle.id,'executor':'temporal','execution_allowed':False}
    except WorkflowAlreadyStartedError:
        return {'job_id':job_id,'workflow_id':job_id,'executor':'temporal','idempotent':True,'execution_allowed':False}


async def worker_main():
 while True:
  worker_state['polling']=False
  worker_state['attempts']+=1
  try:
   c=await Client.connect(TEMP)
   async with Worker(c,task_queue='aiops-runner',workflows=[IncidentWorkflow,ReviewEvidenceWorkflow],activities=[execute_stage,start_run,finish_run, fs_lab_inspect,demo_evidence_phase]):
    worker_state['polling']=True
    worker_state['last_error']=None
    await asyncio.Event().wait()
  except Exception as exc:
   worker_state['polling']=False
   worker_state['last_error']=type(exc).__name__
   log.exception('Temporal polling worker unavailable; retrying in 5s')
   await asyncio.sleep(5)
@app.on_event('startup')
async def startup():
 asyncio.create_task(worker_main())
 asyncio.create_task(reconcile_denial_loop())
