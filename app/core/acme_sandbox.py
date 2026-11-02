"""Core-owned opt-in ACME-TEST sandbox, no human IdP, GLPI write or LIVE effect.

One atomic PG16 transaction persists a canonical synthetic Incident/Run, seven
deduplicated SOURCE observations, two evidence records, fixture analysis/critic
and an immutable attempt. Independent GET recomputes the readback from PG16.
"""
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import os
import re
from urllib.parse import urlsplit
import requests
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
                     "and to_regclass('aiops.acme_sandbox_ticket_events') is not null "
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
    if (tenant != TENANT or aid != attempt or istate not in ('PREPARED', 'RESOLVED')
            or rstatus != istate or synthetic is not True
            or isource != 'SYNTHETIC_SIMULATOR' or source != isource
            or rmode != 'DEMO' or scenario != SCENARIO or riid != incident
            or idem != 'acme-sandbox-v1:' + TENANT + ':' + attempt
            or type(payload) is not dict or payload.get('tenant_id') != TENANT
            or payload.get('attempt_id') != attempt
            or payload.get('mode') != 'SIMULATION'
            or payload.get('human_approved') is not False
            or payload.get('live_effects_allowed') is not False
            or ticket_status != 'PREPARED' or event_count != 7
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
    # RG-ACME-08: independent append-only SIM-GLPI ticket ledger, not Run projection.
    ticket_rows = c.execute(
        "select transition_seq,status,ticket_id,incident_id,run_id,proposal_id,"
        "approval_id,worker_receipt_sha256,terminal_ticket_sha256 "
        "from aiops.acme_sandbox_ticket_events "
        "where tenant_id=%s and attempt_id=%s order by transition_seq",
        (TENANT, attempt)).fetchall()
    prepared = (1, 'PREPARED', ticket, incident, run, proposal, None, None, None)
    if not ticket_rows or tuple(ticket_rows[0]) != prepared:
        raise HTTPException(503, 'sandbox_ticket_prepared_audit_missing')
    terminal = c.execute(
        "select payload from aiops.run_events where run_id=%s "
        "and stage='RUN' and event_type='SIMULATED_RESOLVED' "
        "and status='RESOLVED'", (run,)).fetchall()
    ticket_state, resolved_approval, worker_sha, ticket_sha = 'PREPARED', None, None, None
    if istate == 'RESOLVED':
        if len(ticket_rows) != 2 or len(terminal) != 1:
            raise HTTPException(503, 'sandbox_ticket_terminal_audit_missing')
        final = ticket_rows[1]
        if (tuple(final[:6]) != (2, 'RESOLVED', ticket, incident, run, proposal)
                or type(final[6]) is not str or not final[6].startswith('SIM-APP-')
                or type(final[7]) is not str
                or re.fullmatch(r'[0-9a-f]{64}', final[7].strip()) is None):
            raise HTTPException(503, 'sandbox_ticket_terminal_binding_unqualified')
        resolved_approval, worker_sha = final[6], final[7].strip()
        ticket_sha = digest({
            'schema': 'aiops.portal.sim-glpi-ticket-digest.v1',
            'tenant_id': TENANT, 'attempt_id': attempt,
            'incident_id': incident, 'run_id': run,
            'ticket_id': ticket, 'ticket_status': 'RESOLVED',
            'core_request_sha256': request_hash.strip(),
            'worker_receipt_sha256': worker_sha})
        if final[8] != ticket_sha:
            raise HTTPException(503, 'sandbox_ticket_digest_mismatch')
        event = terminal[0][0]
        if (type(event) is not dict
                or event.get('tenant_id') != TENANT
                or event.get('attempt_id') != attempt
                or event.get('incident_id') != incident
                or event.get('run_id') != run
                or event.get('ticket_id') != ticket
                or event.get('proposal_id') != proposal
                or event.get('approval_id') != resolved_approval
                or event.get('worker_receipt_sha256') != worker_sha
                or event.get('terminal_ticket_sha256') != ticket_sha
                or event.get('worker_receipt_verified') is not True
                or event.get('execution_allowed') is not False
                or event.get('effect_allowed') is not False
                or event.get('human_approved') is not False
                or event.get('live_effects_allowed') is not False):
            raise HTTPException(503, 'sandbox_worker_receipt_digest_mismatch')
        ticket_state = 'RESOLVED'
    elif len(ticket_rows) != 1 or terminal:
        raise HTTPException(503, 'sandbox_premature_terminal_event')
    return {'schema': 'aiops.core-acme-sandbox-readback.v1',
            'attempt_id': attempt, 'tenant_id': TENANT, 'scenario_id': SCENARIO,
            'mode': 'SIMULATION', 'incident_id': incident, 'run_id': run,
            'ticket_id': ticket, 'proposal_id': proposal,
            'incident_status': istate, 'run_status': rstatus,
            'ticket_authority': 'SIMULATED_ONLY', 'glpi_mode': 'SIMULATED_ONLY',
            'ticket_status': ticket_state, 'source': source,
            'analysis_validated': True, 'critic_validated': True,
            'analysis_kind': 'SYNTHETIC_FIXTURE',
            'evidence_count': len(facts), 'source_event_count': len(proofs),
            'source_hashes_qualified': True,
            'source_event_ids': source_ids, 'request_sha256': request_hash.strip(),
            'approval_id': resolved_approval, 'approval_issuer': ISSUER,
            'worker_receipt_sha256': worker_sha,
            'terminal_ticket_receipt_verified': istate == 'RESOLVED',
            'terminal_ticket_sha256': ticket_sha,
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
                  '(%s,%s,%s,%s,%s,now(),NULL,%s,true,%s)',
                  (incident, ident('EXT-SIM-', attempt),
                   'ACME SAN to Payments synthetic sandbox', 'P2', 'PREPARED',
                   'SYNTHETIC_SIMULATOR', Jsonb(incident_payload)))
        c.execute('insert into aiops.runs '
                  '(run_id,incident_id,mode,scenario_id,status,idempotency_key,'
                  'version,started_at,completed_at) '
                  "values (%s,%s,'DEMO',%s,'PREPARED',%s,1,now(),NULL)",
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
                  "values (%s,%s,8,'RUN','SIMULATED_PREPARED','PREPARED',%s,%s)",
                  (ident('EVT-SIM-', attempt + ':prepared'), run,
                   Jsonb({'tenant_id': TENANT, 'synthetic': True,
                          'ticket_id': ticket, 'proposal_id': proposal,
                          'execution_allowed': False, 'effect_allowed': False}),
                   ident('SIM-PREPARED-', attempt)))
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
                   analysis, critique, 'PREPARED', 'SYNTHETIC_SIMULATOR'))
        # RG-ACME-08: immutable ticket PREPARED record exists before any approval.
        c.execute(
            "insert into aiops.acme_sandbox_ticket_events "
            "(tenant_id,attempt_id,transition_seq,status,ticket_id,incident_id,"
            "run_id,proposal_id) values (%s,%s,1,'PREPARED',%s,%s,%s,%s)",
            (TENANT, attempt, ticket, incident, run, proposal))
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

def independent_readback(component, attempt):
    """Only fixed internal sandbox service URLs; never a caller URL or LIVE."""
    env, default, allowed, port = {
        'worker': ('WORKER_URL', 'http://aiops2-worker:815',
                   {'aiops2-worker', 'aiops2-rebuild-worker', 'localhost', '127.0.0.1'}, 815),
        'twin': ('TWIN_URL', 'http://aiops2-twin:811',
                 {'aiops2-twin', 'aiops2-rebuild-twin', 'localhost', '127.0.0.1'}, 811),
        'policy': ('POLICY_URL', 'http://aiops2-policy:813',
                   {'aiops2-policy', 'aiops2-rebuild-policy', 'localhost', '127.0.0.1'}, 813),
    }[component]
    base = os.getenv(env, default).rstrip('/')
    # RG-ACME-18: parse port defensively before forwarding a shared bearer.
    # Invalid IPv6/port syntax must fail closed with 503, never raise a 500.
    try:
        parsed = urlsplit(base)
        valid_origin = (
            parsed.scheme in ('http', 'https')
            and parsed.hostname in allowed and parsed.port == port
            and not parsed.username and not parsed.password
            and not parsed.path and not parsed.query and not parsed.fragment)
    except ValueError:
        valid_origin = False
    if not valid_origin:
        raise HTTPException(503, 'sandbox_service_url_invalid')
    try:
        response = requests.get(
            base + '/api/sandbox/acme/e2e/' + attempt,
            headers={'Authorization': 'Bearer ' + os.environ['AIOPS_INTERNAL_TOKEN'],
                     'Accept': 'application/json'},
            timeout=5, allow_redirects=False)
        if response.status_code != 200 or len(response.content) > 32768:
            raise ValueError('status_or_size')
        value = response.json()
        if type(value) is not dict:
            raise ValueError('shape')
        return value
    except (requests.RequestException, ValueError, KeyError):
        raise HTTPException(503, 'sandbox_' + component + '_readback_unavailable') from None

def approval_fresh(twin):
    """RG-ACME-09: Core independently fences stale/future Twin authority."""
    try:
        issued = datetime.fromisoformat(twin['issued_at'])
        expires = datetime.fromisoformat(twin['expires_at'])
    except (KeyError, TypeError, ValueError):
        raise HTTPException(503, 'sandbox_approval_clock_unqualified') from None
    now = datetime.now(timezone.utc)
    if (issued.tzinfo is None or expires.tzinfo is None
            or issued.utcoffset() != timedelta(0)
            or expires.utcoffset() != timedelta(0)
            or issued > now + timedelta(seconds=30)
            or expires <= now or expires <= issued
            or expires - issued > timedelta(minutes=5)
            or now - issued > timedelta(minutes=5)
            or type(twin.get('approval_nonce')) is not str
            or not twin['approval_nonce'].startswith('SIMNONCE-')):
        raise HTTPException(503, 'sandbox_approval_stale_or_unqualified')

@router.post('/api/sandbox/acme/resolve')
def resolve(x: Intent, authorization: str | None = Header(default=None)):
    """RG-ACME-09: only Core commits after authenticated Temporal no-effect."""
    require_enabled()
    auth(authorization)
    validate(x)
    attempt = x.attempt_id
    request_hash = digest(x.model_dump())
    # Replay is proved from durable PG16, not from a newly forged Worker reply.
    with db() as c:
        c.execute('select pg_advisory_xact_lock(hashtextextended(%s,0))',
                  ('core-acme-sandbox:' + TENANT + ':' + attempt,))
        if not schema_ready(c):
            raise HTTPException(503, 'core_sandbox_schema_unavailable')
        record = row(c, attempt)
        if record is None:
            raise HTTPException(404, 'sandbox_attempt_not_found')
        if record[2].strip() != request_hash:
            raise HTTPException(409, 'sandbox_attempt_rebinding_denied')
        current = read(c, attempt)
        if current['run_status'] == 'RESOLVED':
            current['idempotent'] = True
            return current
        if (current['run_status'] != 'PREPARED'
                or current['incident_status'] != 'PREPARED'
                or current['ticket_status'] != 'PREPARED'):
            raise HTTPException(503, 'sandbox_core_not_prepared')

    # Worker GET is backed by completed Temporal history; read it twice and
    # bind the exact JSON digest. Caller-supplied receipts are never accepted.
    worker = independent_readback('worker', attempt)
    twin = independent_readback('twin', attempt)
    policy = independent_readback('policy', attempt)
    second_worker = independent_readback('worker', attempt)
    if (any(type(d) is not dict for d in (worker, twin, policy, second_worker))
            or worker != second_worker
            or any(d.get('attempt_id') != attempt or d.get('tenant_id') != TENANT
                   for d in (worker, twin, policy))):
        raise HTTPException(503, 'sandbox_cross_tenant_or_worker_rotation')
    approval = worker.get('approval_id')
    if (type(approval) is not str or not approval.startswith('SIM-APP-')
            or twin.get('approval_id') != approval
            or policy.get('approval_id') != approval
            or worker.get('schema') != 'aiops.worker-acme-simulated-no-effect.v1'
            or worker.get('receipt_status') != 'SIMULATED_NO_EFFECT'
            or worker.get('receipt_phase') != 'PRE_RESOLUTION'
            or worker.get('core_status_at_validation') != 'PREPARED'
            or worker.get('resolution_verified') is not False
            or worker.get('post_resolution_readback_required') is not True
            or worker.get('action') != 'SIMULATE'
            or type(worker.get('effect_receipts')) is not int
            or worker.get('effect_receipts') != 0
            or worker.get('approval_kind') != 'SIMULATED'
            or worker.get('approval_issuer') != ISSUER
            or worker.get('audit_authority') != 'TEMPORAL_WORKFLOW_HISTORY_ONLY'
            or worker.get('audit_transitions') != [
                'CORE_PREPARED_INDEPENDENTLY_VERIFIED',
                'TWIN_SIMULATED_APPROVAL_VALIDATED',
                'POLICY_SIMULATE_INDEPENDENTLY_VERIFIED',
                'WORKER_NO_EFFECT']
            or worker.get('core_014_015_written') is not False
            or worker.get('glpi_write') is not False
            or twin.get('issuer_id') != 'twin-acme-test'
            or twin.get('approval_actor') != ISSUER
            or twin.get('approval_status') != 'SIMULATED'
            or twin.get('approval_kind') != 'SIMULATED'
            or twin.get('approval_issuer') != ISSUER
            or twin.get('approval_phase') != 'PRE_RESOLUTION'
            or twin.get('core_status_at_issuance') != 'PREPARED'
            or twin.get('resolution_verified') is not False
            or twin.get('post_resolution_readback_required') is not True
            or policy.get('state') != 'PASS'
            or policy.get('mode') != 'SIMULATION'
            or policy.get('decision') != 'SIMULATE'
            or policy.get('approval_kind') != 'SIMULATED'
            or policy.get('approval_issuer') != ISSUER
            or any(d.get(k) is not False for d in (worker, twin, policy)
                   for k in ('human_approved', 'execution_allowed',
                             'effect_allowed', 'live_effects_allowed',
                             'real_glpi_writes_allowed'))):
        raise HTTPException(503, 'sandbox_no_effect_authority_unqualified')
    approval_fresh(twin)
    # #348 Worker contract: receipt digest is canonical and source/nonce bound.
    worker_sha = worker.get('receipt_sha256')
    body = {k: v for k, v in worker.items() if k != 'receipt_sha256'}
    nonce = twin.get('approval_nonce')
    if (type(worker_sha) is not str
            or re.fullmatch(r'[0-9a-f]{64}', worker_sha) is None
            or not hmac.compare_digest(digest(body), worker_sha)
            or worker.get('core_request_sha256') != current['request_sha256']
            or worker.get('core_source_event_ids') != current['source_event_ids']
            or type(nonce) is not str or not nonce.isascii()
            or worker.get('twin_approval_nonce_sha256') !=
                hashlib.sha256(nonce.encode('ascii')).hexdigest()):
        raise HTTPException(503, 'sandbox_worker_canonical_receipt_unqualified')
    with db() as c:
        c.execute('select pg_advisory_xact_lock(hashtextextended(%s,0))',
                  ('core-acme-sandbox:' + TENANT + ':' + attempt,))
        if not schema_ready(c):
            raise HTTPException(503, 'core_sandbox_schema_unavailable')
        record = row(c, attempt)
        if record is None or record[2].strip() != request_hash:
            raise HTTPException(409, 'sandbox_attempt_rebinding_denied')
        current = read(c, attempt)
        if current['run_status'] == 'RESOLVED':
            current['idempotent'] = True
            return current
        for doc in (worker, twin, policy):
            if any(doc.get(k) != current[k] for k in
                   ('incident_id', 'run_id', 'proposal_id')):
                raise HTTPException(503, 'sandbox_independent_identity_mismatch')
        if (twin.get('ticket_id') != current['ticket_id']
                or policy.get('ticket_id') != current['ticket_id']
                or twin.get('core_request_sha256') != current['request_sha256']
                or twin.get('core_source_event_ids') != current['source_event_ids']
                or worker.get('core_request_sha256') != current['request_sha256']
                or worker.get('core_source_event_ids') != current['source_event_ids']
                or current['source_hashes_qualified'] is not True
                or current['approval_id'] is not None
                or current['ticket_status'] != 'PREPARED'):
            raise HTTPException(503, 'sandbox_simulated_ticket_or_source_mismatch')
        incident, run, ticket, proposal = (
            current[k] for k in ('incident_id', 'run_id', 'ticket_id', 'proposal_id'))
        changed = c.execute(
            "update aiops.incidents set state='RESOLVED',resolved_at=now() "
            "where incident_id=%s and state='PREPARED'", (incident,))
        if changed.rowcount != 1:
            raise HTTPException(503, 'sandbox_incident_transition_conflict')
        changed = c.execute(
            "update aiops.runs set status='RESOLVED',completed_at=now(),"
            "version=version+1 where run_id=%s and status='PREPARED'", (run,))
        if changed.rowcount != 1:
            raise HTTPException(503, 'sandbox_run_transition_conflict')
        # Separate immutable SIM-GLPI terminal record; 016 attempt remains immutable.
        ticket_sha = digest({
            'schema': 'aiops.portal.sim-glpi-ticket-digest.v1',
            'tenant_id': TENANT, 'attempt_id': attempt,
            'incident_id': incident, 'run_id': run,
            'ticket_id': ticket, 'ticket_status': 'RESOLVED',
            'core_request_sha256': current['request_sha256'],
            'worker_receipt_sha256': worker_sha})
        c.execute(
            "insert into aiops.acme_sandbox_ticket_events "
            "(tenant_id,attempt_id,transition_seq,status,ticket_id,incident_id,"
            "run_id,proposal_id,approval_id,worker_receipt_sha256,terminal_ticket_sha256) "
            "values (%s,%s,2,'RESOLVED',%s,%s,%s,%s,%s,%s,%s)",
            (TENANT, attempt, ticket, incident, run, proposal, approval, worker_sha, ticket_sha))
        c.execute(
            "insert into aiops.run_events "
            "(event_id,run_id,sequence,stage,event_type,status,payload,event_key) "
            "values (%s,%s,9,'RUN','SIMULATED_RESOLVED','RESOLVED',%s,%s)",
            (ident('EVT-SIM-', attempt + ':resolved'), run,
             Jsonb({'tenant_id': TENANT, 'attempt_id': attempt,
                    'incident_id': incident, 'run_id': run,
                    'ticket_id': ticket, 'proposal_id': proposal,
                    'approval_id': approval, 'worker_receipt_sha256': worker_sha,
                    'terminal_ticket_sha256': ticket_sha,
                    'worker_receipt_verified': True, 'execution_allowed': False,
                    'effect_allowed': False, 'human_approved': False,
                    'live_effects_allowed': False}),
             ident('SIM-RESOLVED-', attempt)))
        result = read(c, attempt)
        result['idempotent'] = False
        return result
