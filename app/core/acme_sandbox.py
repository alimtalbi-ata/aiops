"""Core-owned opt-in ACME-TEST sandbox, no human IdP, GLPI write or LIVE effect.

One atomic PG16 transaction persists a canonical synthetic Incident/Run, seven
deduplicated SOURCE observations, two evidence records, fixture analysis/critic
and an immutable attempt. Independent GET recomputes the readback from PG16.
"""
import hashlib
import hmac
import json
import os
import re
from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from psycopg.types.json import Jsonb
from shared.db import db

router = APIRouter()
TENANT, SCENARIO, ISSUER = 'ACME-TEST', 'ACME-SAN-PAYMENTS', 'TWIN_ACME_SIMULATED'
CAP_SCHEMA = 'aiops.acme-sandbox-capabilities.v1'
ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9_-]{2,99}\Z', re.ASCII)
HEADERS = {'Cache-Control': 'no-store', 'Pragma': 'no-cache',
           'X-Content-Type-Options': 'nosniff'}

def canonical(v):
    return json.dumps(v, sort_keys=True, separators=(',', ':'), ensure_ascii=True)

def digest(v):
    return hashlib.sha256(canonical(v).encode()).hexdigest()

def ident(prefix, attempt, length=24):
    return prefix + hashlib.sha256((TENANT + ':' + attempt).encode()).hexdigest()[:length].upper()

def enabled():
    token = os.getenv('AIOPS_INTERNAL_TOKEN', '')
    return (os.getenv('AIOPS_ACME_SANDBOX_ENABLED') == 'true'
            and 32 <= len(token) <= 256 and token.isascii()
            and not any(c.isspace() for c in token))

def require_enabled():
    if not enabled():
        raise HTTPException(503, 'core_sandbox_disabled')

def auth(authorization):
    secret = os.getenv('AIOPS_INTERNAL_TOKEN', '')
    scheme, sep, supplied = (authorization or '').partition(' ')
    if (scheme.lower() != 'bearer' or not sep or not supplied
            or len(supplied) > 256 or not supplied.isascii()
            or not hmac.compare_digest(secret, supplied)):
        raise HTTPException(401, 'sandbox_service_auth_required')

class Intent(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    attempt_id: str = Field(pattern=r'^[A-Za-z0-9][A-Za-z0-9_-]{2,99}$')
    tenant_id: str
    scenario_id: str
    mode: str
    approval_issuer: str
    idempotency_key: str
    live_effects_allowed: bool

def validate(x):
    if (x.tenant_id != TENANT or x.scenario_id != SCENARIO
            or x.mode != 'SIMULATION' or x.approval_issuer != ISSUER
            or x.idempotency_key != x.attempt_id
            or x.live_effects_allowed is not False):
        raise HTTPException(403, 'sandbox_scope_or_effect_denied')

def schema_ready(c):
    return c.execute("select to_regclass('aiops.acme_sandbox_attempts') is not null "
                     "and to_regclass('aiops.ux_run_events_event_key') is not null "
                     "and exists (select 1 from pg_attribute "
                     "where attrelid=to_regclass('aiops.run_events') "
                     "and attname='event_key' and not attisdropped)").fetchone()[0]

def row(c, attempt):
    return c.execute(
        'select tenant_id,attempt_id,request_sha256,incident_id,run_id,'
        'ticket_id,proposal_id,analysis_id,critique_id,ticket_status,source,'
        'evidence_count,source_event_count from aiops.acme_sandbox_attempts '
        'where tenant_id=%s and attempt_id=%s', (TENANT, attempt)).fetchone()

def read(c, attempt):
    r = row(c, attempt)
    if r is None:
        raise HTTPException(404, 'sandbox_attempt_not_found')
    (tenant, aid, request_hash, incident, run, ticket, proposal, analysis,
     critique, ticket_status, source, evidence_count, event_count) = r
    canonical_row = c.execute(
        'select i.state,i.synthetic,i.source,i.payload,r.status,r.mode,'
        'r.incident_id,r.scenario_id,r.idempotency_key '
        'from aiops.incidents i join aiops.runs r on r.incident_id=i.incident_id '
        'where i.incident_id=%s and r.run_id=%s', (incident, run)).fetchone()
    if not canonical_row:
        raise HTTPException(503, 'sandbox_canonical_identity_missing')
    istate, synthetic, isource, payload, rstatus, rmode, riid, scenario, idem = canonical_row
    if (tenant != TENANT or aid != attempt or istate != 'RESOLVED'
            or rstatus != 'RESOLVED' or synthetic is not True
            or isource != 'SYNTHETIC_SIMULATOR' or source != isource
            or rmode != 'DEMO' or scenario != SCENARIO or riid != incident
            or idem != 'acme-sandbox-v1:' + TENANT + ':' + attempt
            or type(payload) is not dict or payload.get('tenant_id') != TENANT
            or payload.get('attempt_id') != attempt
            or payload.get('mode') != 'SIMULATION'
            or payload.get('human_approved') is not False
            or payload.get('live_effects_allowed') is not False
            or ticket_status != 'RESOLVED' or event_count != 7
            or evidence_count != 2):
        raise HTTPException(503, 'sandbox_identity_or_status_unqualified')
    proofs = c.execute(
        "select event_key,payload,evidence_ids from aiops.run_events "
        "where run_id=%s and stage='SOURCE' and event_type='OBSERVED' "
        "and status='PASS' order by sequence", (run,)).fetchall()
    if len(proofs) != 7:
        raise HTTPException(503, 'sandbox_source_count_unqualified')
    source_ids, linked_evidence = [], []
    for index, (key, event, eids) in enumerate(proofs, 1):
        expected = ident('SYN-EVT-', attempt + ':' + str(index), 20)
        payload_hash = digest({'tenant_id': TENANT, 'run_id': run,
                               'sequence': index, 'source': 'SYNTHETIC_SIMULATOR'})
        full_hash = digest({'source_event_id': expected,
                            'payload_sha256': payload_hash})
        if (key != expected or type(event) is not dict
                or event.get('tenant_id') != TENANT
                or event.get('incident_id') != incident
                or event.get('run_id') != run
                or event.get('source_event_id') != key
                or event.get('sequence') != index
                or event.get('source') != 'SYNTHETIC_SIMULATOR'
                or event.get('synthetic') is not True
                or event.get('source_issuer') != 'sandbox-simulator'
                or event.get('actor_issuer') != 'sandbox-simulated-actor'
                or event.get('payload_sha256') != payload_hash
                or event.get('full_event_sha256') != full_hash
                or full_hash == payload_hash
                or type(eids) is not list or len(eids) != 1):
            raise HTTPException(503, 'sandbox_source_binding_unqualified')
        source_ids.append(key)
        linked_evidence.append(eids[0])
    facts = c.execute(
        "select evidence_id,provenance,observed_at,known_at,statement_timestamp() from aiops.evidence "
        "where provenance->>'sandbox_attempt_id'=%s "
        "and provenance->>'tenant_id'=%s and provenance->>'run_id'=%s",
        (attempt, TENANT, run)).fetchall()
    evidence_ids = sorted(r[0] for r in facts)
    if (len(facts) != 2 or set(evidence_ids) !=
            {ident('EVID-SIM-', attempt + ':' + str(i)) for i in (1, 2)}
            or any(f[1].get('incident_id') != incident for f in facts)
            or any(eid not in evidence_ids for eid in linked_evidence)
            or any(f[2] is None or f[3] is None or
                   not (0 <= (f[3]-f[2]).total_seconds() <= 300)
                   or not (0 <= (f[4]-f[2]).total_seconds() <= 300) for f in facts)):
        raise HTTPException(503, 'sandbox_evidence_unqualified')
    ar = c.execute('select status,provider,evidence_ids,output from aiops.analysis_records '
                   'where analysis_id=%s and run_id=%s and incident_id=%s',
                   (analysis, run, incident)).fetchone()
    cr = c.execute('select validated,provider,evidence_ids,output,analysis_id '
                   'from aiops.critique_records where critique_id=%s and run_id=%s',
                   (critique, run)).fetchone()
    if (not ar or ar[0] != 'VALID' or ar[1] != 'sandbox-synthetic-fixture'
            or sorted(ar[2]) != evidence_ids or ar[3].get('synthetic') is not True
            or not cr or cr[0] is not True or cr[1] != 'sandbox-synthetic-fixture'
            or sorted(cr[2]) != evidence_ids or cr[3].get('synthetic') is not True
            or cr[4] != analysis):
        raise HTTPException(503, 'sandbox_analysis_critic_unqualified')
    return {'schema': 'aiops.core-acme-sandbox-readback.v1',
            'attempt_id': attempt, 'tenant_id': TENANT, 'scenario_id': SCENARIO,
            'mode': 'SIMULATION', 'incident_id': incident, 'run_id': run,
            'ticket_id': ticket, 'proposal_id': proposal,
            'incident_status': istate, 'run_status': rstatus,
            'ticket_authority': 'SIMULATED_ONLY', 'glpi_mode': 'SIMULATED_ONLY',
            'ticket_status': ticket_status, 'source': source,
            'analysis_validated': True, 'critic_validated': True,
            'analysis_kind': 'SYNTHETIC_FIXTURE',
            'evidence_count': len(facts), 'source_event_count': len(proofs),
            'source_hashes_qualified': True,
            'source_event_ids': source_ids, 'request_sha256': request_hash.strip(),
            'approval_id': None, 'approval_issuer': ISSUER,
            'human_approval_claimed': False, 'human_approved': False,
            'live_effects_allowed': False, 'real_glpi_writes_allowed': False,
            'execution_allowed': False, 'effect_allowed': False}

@router.get('/api/sandbox/acme/capabilities')
def capabilities():
    require_enabled()
    try:
        with db() as c:
            if not schema_ready(c):
                raise HTTPException(503, 'core_sandbox_schema_unavailable')
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(503, 'core_sandbox_schema_unavailable') from None
    return {'schema': CAP_SCHEMA, 'component': 'core', 'tenant_id': TENANT,
            'mode': 'SIMULATION', 'isolated': True, 'approval_issuer': ISSUER,
            'human_approval_claimed': False, 'live_effects_allowed': False,
            'real_glpi_writes_allowed': False}

@router.post('/api/sandbox/acme/e2e')
def start(x: Intent, authorization: str | None = Header(default=None)):
    require_enabled()
    auth(authorization)
    validate(x)
    attempt = x.attempt_id
    request_hash = digest(x.model_dump())
    incident, run = ident('INC-SIM-', attempt), ident('RUN-SIM-', attempt)
    ticket, proposal = ident('SIM-GLPI-', attempt), ident('PROP-SIM-', attempt)
    analysis, critique = ident('AN-SIM-', attempt), ident('CR-SIM-', attempt)
    with db() as c:
        c.execute('select pg_advisory_xact_lock(hashtextextended(%s,0))',
                  ('core-acme-sandbox:' + TENANT + ':' + attempt,))
        if not schema_ready(c):
            raise HTTPException(503, 'core_sandbox_schema_unavailable')
        old = row(c, attempt)
        if old:
            if old[2].strip() != request_hash:
                raise HTTPException(409, 'sandbox_attempt_rebinding_denied')
            result = read(c, attempt)
            result['idempotent'] = True
            return result
        incident_payload = {'tenant_id': TENANT, 'attempt_id': attempt,
                            'mode': 'SIMULATION', 'synthetic': True,
                            'human_approved': False, 'live_effects_allowed': False,
                            'ticket_authority': 'SIMULATED_ONLY'}
        c.execute('insert into aiops.incidents '
                  '(incident_id,external_id,title,severity,state,opened_at,resolved_at,'
                  'source,synthetic,payload) values '
                  '(%s,%s,%s,%s,%s,now(),now(),%s,true,%s)',
                  (incident, ident('EXT-SIM-', attempt),
                   'ACME SAN to Payments synthetic sandbox', 'P2', 'RESOLVED',
                   'SYNTHETIC_SIMULATOR', Jsonb(incident_payload)))
        c.execute('insert into aiops.runs '
                  '(run_id,incident_id,mode,scenario_id,status,idempotency_key,'
                  'version,started_at,completed_at) '
                  "values (%s,%s,'DEMO',%s,'RESOLVED',%s,9,now(),now())",
                  (run, incident, SCENARIO,
                   'acme-sandbox-v1:' + TENANT + ':' + attempt))
        evidence_ids = []
        for index in (1, 2):
            key = ident('SYN-EVT-', attempt + ':' + str(index), 20)
            eid = ident('EVID-SIM-', attempt + ':' + str(index))
            evidence_ids.append(eid)
            envelope = {'tenant_id': TENANT, 'attempt_id': attempt,
                        'run_id': run, 'incident_id': incident,
                        'source_event_id': key, 'sequence': index,
                        'source': 'SYNTHETIC_SIMULATOR', 'synthetic': True}
            c.execute('insert into aiops.evidence '
                      '(evidence_id,source,external_id,observed_at,claim,confidence,'
                      'provenance,payload_hash,payload) '
                      'values (%s,%s,%s,now(),%s,1,%s,%s,%s)',
                      (eid, 'SYNTHETIC_SIMULATOR', key,
                       'synthetic sandbox SAN observation',
                       Jsonb({'tenant_id': TENANT, 'sandbox_attempt_id': attempt,
                              'run_id': run, 'incident_id': incident,
                              'issuer': 'sandbox-simulator', 'synthetic': True}),
                       digest(envelope), Jsonb(envelope)))
        for index in range(1, 8):
            key = ident('SYN-EVT-', attempt + ':' + str(index), 20)
            payload_hash = digest({'tenant_id': TENANT, 'run_id': run,
                                   'sequence': index, 'source': 'SYNTHETIC_SIMULATOR'})
            full_hash = digest({'source_event_id': key,
                                'payload_sha256': payload_hash})
            envelope = {'tenant_id': TENANT, 'incident_id': incident,
                        'run_id': run, 'source_event_id': key,
                        'payload_sha256': payload_hash,
                        'full_event_sha256': full_hash,
                        'sequence': index, 'source': 'SYNTHETIC_SIMULATOR',
                        'synthetic': True, 'source_issuer': 'sandbox-simulator',
                        'actor_issuer': 'sandbox-simulated-actor'}
            c.execute('insert into aiops.run_events '
                      '(event_id,run_id,sequence,stage,event_type,status,'
                      'evidence_ids,payload,event_key) '
                      "values (%s,%s,%s,'SOURCE','OBSERVED','PASS',%s,%s,%s)",
                      (ident('EVT-SIM-', attempt + ':' + str(index)), run,
                       index, Jsonb([evidence_ids[(index - 1) % 2]]),
                       Jsonb(envelope), key))
        c.execute('insert into aiops.run_events '
                  '(event_id,run_id,sequence,stage,event_type,status,payload,event_key) '
                  "values (%s,%s,8,'RUN','SIMULATED_RESOLVED','RESOLVED',%s,%s)",
                  (ident('EVT-SIM-', attempt + ':resolved'), run,
                   Jsonb({'tenant_id': TENANT, 'synthetic': True,
                          'ticket_id': ticket, 'proposal_id': proposal,
                          'execution_allowed': False, 'effect_allowed': False}),
                   ident('SIM-RESOLVED-', attempt)))
        c.execute('insert into aiops.analysis_records '
                  '(analysis_id,run_id,incident_id,idempotency_key,revision,'
                  'contract_version,provider,model,prompt_version,evidence_ids,'
                  'evidence_set_hash,output,confidence,status) '
                  'values (%s,%s,%s,%s,1,%s,%s,%s,%s,%s,%s,%s,1,%s)',
                  (analysis, run, incident, ident('AN-IDEMP-', attempt),
                   'sandbox-synthetic-v1', 'sandbox-synthetic-fixture',
                   'no-model', 'fixture-v1', Jsonb(evidence_ids),
                   digest(evidence_ids),
                   Jsonb({'synthetic': True, 'advisory_only': True,
                          'human_authority': False}), 'VALID'))
        c.execute('insert into aiops.critique_records '
                  '(critique_id,idempotency_key,analysis_id,run_id,contract_version,'
                  'provider,model,validated,issues,evidence_ids,output,'
                  'diagnostic_confidence) '
                  'values (%s,%s,%s,%s,%s,%s,%s,true,%s,%s,%s,1)',
                  (critique, ident('CR-IDEMP-', attempt), analysis, run,
                   'sandbox-synthetic-v1', 'sandbox-synthetic-fixture',
                   'no-model', Jsonb([]), Jsonb(evidence_ids),
                   Jsonb({'synthetic': True, 'advisory_only': True})))
        c.execute('insert into aiops.acme_sandbox_attempts '
                  '(tenant_id,attempt_id,request_sha256,incident_id,run_id,'
                  'ticket_id,proposal_id,analysis_id,critique_id,ticket_status,'
                  'source,evidence_count,source_event_count) '
                  'values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,2,7)',
                  (TENANT, attempt, request_hash, incident, run, ticket, proposal,
                   analysis, critique, 'RESOLVED', 'SYNTHETIC_SIMULATOR'))
        result = read(c, attempt)
        result['idempotent'] = False
        return result

@router.get('/api/sandbox/acme/e2e/{attempt_id}')
def readback(attempt_id: str, authorization: str | None = Header(default=None)):
    require_enabled()
    auth(authorization)
    if type(attempt_id) is not str or ID.fullmatch(attempt_id) is None:
        raise HTTPException(422, 'invalid_sandbox_attempt')
    try:
        with db() as c:
            return JSONResponse(read(c, attempt_id), headers=HEADERS)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(503, 'sandbox_readback_unavailable') from None
