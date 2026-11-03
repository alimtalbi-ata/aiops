"""Internal-only, read-only Core ACME same-Run journey from one PG16 snapshot.

Projection of existing Core sandbox; NOT a new Run store, launcher, browser ACL,
human approval, independently attested Analyst/Critic, or LIVE observation.
"""
from datetime import datetime, timezone
import hashlib
import json

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import JSONResponse
from core import acme_sandbox as core
from shared.db import db

router = APIRouter()


def project_journey(snapshot, rows, attempt):
    """Refuse mixed Run/tenant, reordered SOURCE, extra events or forged terminal."""
    if (type(snapshot) is not dict
            or snapshot.get('schema') != 'aiops.core-acme-sandbox-readback.v1'
            or snapshot.get('tenant_id') != core.TENANT
            or snapshot.get('scenario_id') != core.SCENARIO
            or snapshot.get('attempt_id') != attempt
            or snapshot.get('mode') != 'SIMULATION'
            or snapshot.get('source') != 'SYNTHETIC_SIMULATOR'
            or snapshot.get('source_hashes_qualified') is not True
            or snapshot.get('ticket_authority') != 'SIMULATED_ONLY'
            or snapshot.get('approval_issuer') != core.ISSUER
            or any(snapshot.get(key) is not False for key in
                   ('human_approved', 'live_effects_allowed',
                    'real_glpi_writes_allowed', 'execution_allowed', 'effect_allowed'))
            or snapshot.get('run_status') not in ('PREPARED', 'RESOLVED')
            or snapshot.get('incident_status') != snapshot.get('run_status')
            or type(snapshot.get('source_event_count')) is not int
            or snapshot['source_event_count'] != 7
            or type(snapshot.get('source_event_ids')) is not list
            or len(snapshot['source_event_ids']) != 7
            or snapshot['source_event_ids'] != [
                core.ident('SYN-EVT-', attempt + ':' + str(i), 20)
                for i in range(1, 8)]
            or any(type(snapshot.get(k)) is not str for k in
                   ('incident_id', 'run_id', 'ticket_id', 'proposal_id', 'request_sha256'))):
        raise HTTPException(503, 'sandbox_journey_core_unqualified')
    resolved = snapshot['run_status'] == 'RESOLVED'
    if (len(rows) != (9 if resolved else 8)
            or snapshot.get('worker_receipt_verified') is not resolved
            or snapshot.get('terminal_ticket_receipt_verified') is not resolved):
        raise HTTPException(503, 'sandbox_journey_event_count_unqualified')
    # These are synthetic Core evidence references, not evidence bytes or
    # independently observed SAN facts. Never promote them to Analyst/Critic.
    expected_evidence = {
        core.ident('EVID-SIM-', attempt + ':' + str(i)) for i in (1, 2)
    }
    timeline = []
    last_time = None
    for index, row in enumerate(rows, 1):
        if type(row) not in (tuple, list) or len(row) != 8:
            raise HTTPException(503, 'sandbox_journey_event_unqualified')
        seq, stage, kind, status, occurred, event_key, evidence, payload = row
        if (type(seq) is not int or seq != index
                or not isinstance(occurred, datetime) or occurred.tzinfo is None
                or occurred.utcoffset() is None or type(payload) is not dict
                or type(evidence) is not list
                or payload.get('tenant_id') != core.TENANT):
            raise HTTPException(503, 'sandbox_journey_event_unqualified')
        utc = occurred.astimezone(timezone.utc)
        if last_time is not None and utc < last_time:
            raise HTTPException(503, 'sandbox_journey_time_order_unqualified')
        last_time = utc
        if index <= 7:
            if (stage, kind, status) != ('SOURCE', 'OBSERVED', 'PASS') or (
                    event_key != snapshot['source_event_ids'][index - 1]
                    or payload.get('source_event_id') != event_key
                    or payload.get('run_id') != snapshot['run_id']
                    or payload.get('incident_id') != snapshot['incident_id']
                    or type(payload.get('sequence')) is not int
                    or payload.get('sequence') != index
                    or payload.get('synthetic') is not True
                    or len(evidence) != 1
                    or type(evidence[0]) is not str
                    or evidence[0] not in expected_evidence
                    # The Core producer alternates EVID-SIM-1/2 by sequence;
                    # set membership alone would accept swapped provenance.
                    or evidence[0] != core.ident(
                        'EVID-SIM-', attempt + ':' + str(1 + ((index - 1) % 2)))):
                raise HTTPException(503, 'sandbox_journey_source_unqualified')
        elif index == 8:
            if ((stage, kind, status) != ('RUN', 'SIMULATED_PREPARED', 'PREPARED')
                    or event_key != core.ident('SIM-PREPARED-', attempt)
                    or payload.get('synthetic') is not True
                    or payload.get('ticket_id') != snapshot['ticket_id']
                    or payload.get('proposal_id') != snapshot['proposal_id']
                    or payload.get('execution_allowed') is not False
                    or payload.get('effect_allowed') is not False
                    or evidence):
                raise HTTPException(503, 'sandbox_journey_prepared_unqualified')
        else:
            if ((stage, kind, status) != ('RUN', 'SIMULATED_RESOLVED', 'RESOLVED')
                    or event_key != core.ident('SIM-RESOLVED-', attempt)
                    or payload.get('approval_id') != snapshot.get('approval_id')
                    or payload.get('worker_receipt_verified') is not True
                    or payload.get('worker_receipt_sha256') != snapshot.get('worker_receipt_sha256')
                    or payload.get('terminal_ticket_sha256') != snapshot.get('terminal_ticket_sha256')
                    or payload.get('execution_allowed') is not False
                    or payload.get('effect_allowed') is not False
                    or evidence):
                raise HTTPException(503, 'sandbox_journey_terminal_unqualified')
        # Local DB digest for repeated-readback comparison, not a signature.
        record = {'sequence': seq, 'stage': stage, 'event_type': kind,
                  'status': status, 'occurred_at_utc': utc.isoformat(),
                  'event_key': event_key, 'evidence_ids': evidence, 'payload': payload}
        fingerprint = hashlib.sha256(json.dumps(
            record, sort_keys=True, separators=(',', ':'), ensure_ascii=True
        ).encode()).hexdigest()
        timeline.append({'sequence': seq, 'stage': stage, 'event_type': kind,
                         'status': status, 'occurred_at_utc': utc.isoformat(),
                         'source_event_id': event_key if index <= 7 else None,
                         'event_key': event_key,
                         'evidence_ids': list(evidence),
                         'record_sha256': fingerprint})
    # Stable comparison key for NOC/Studio/Twin consumers once an independent
    # server-side actor/tenant/exact-Run ACL exists. SHA256 is NOT a signature.
    journey_fingerprint = hashlib.sha256(json.dumps({
        'tenant_id': core.TENANT, 'attempt_id': attempt,
        'incident_id': snapshot['incident_id'], 'run_id': snapshot['run_id'],
        'timeline': timeline,
    }, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()).hexdigest()
    return {
        'schema': 'aiops.core-acme-sandbox-journey.v1',
        'tenant_id': core.TENANT, 'attempt_id': attempt,
        'scenario_id': core.SCENARIO, 'mode': 'SIMULATION',
        'incident_id': snapshot['incident_id'], 'run_id': snapshot['run_id'],
        'ticket_id': snapshot['ticket_id'], 'ticket_authority': 'SIMULATED_ONLY',
        'run_status': snapshot['run_status'], 'source_event_ids': list(snapshot['source_event_ids']),
        'source_event_count': 7, 'timeline': timeline,
        'source_evidence_refs': sorted({eid for event in timeline[:7]
                                        for eid in event['evidence_ids']}),
        'source_evidence_authority': 'CORE_PG16_SYNTHETIC_FIXTURE_REFS_ONLY',
        'source_evidence_independently_attested': False,
        'journey_sha256': journey_fingerprint,
        'journey_digest_kind': 'LOCAL_CORE_READBACK_SHA256_NOT_SIGNATURE',
        'readback_authority': 'CORE_PG16_INTERNAL_BEARER_ONLY',
        'event_digest_kind': 'LOCAL_DB_READBACK_SHA256_NOT_SIGNATURE',
        'analyst': 'SYNTHETIC_FIXTURE_NOT_INDEPENDENTLY_ATTESTED',
        'critic': 'SYNTHETIC_FIXTURE_NOT_INDEPENDENTLY_ATTESTED',
        'policy': 'NOT_INDEPENDENTLY_READ_BY_THIS_ENDPOINT',
        'twin_graph_019': 'NOT_BOUND_TO_THIS_RUN',
        'worker': 'CORE_VERIFIED_SIMULATED_NO_EFFECT_RECEIPT' if resolved else 'NOT_YET_VERIFIED',
        'scenario_replay': 'READBACK_ONLY_NOT_A_SCENARIO_LAUNCH',
        'human_approved': False, 'live_effects_allowed': False,
        'real_glpi_writes_allowed': False, 'effect_allowed': False,
    }


@router.get('/api/sandbox/acme/e2e/{attempt_id}/journey')
def journey(attempt_id: str, authorization: str | None = Header(default=None)):
    core.require_enabled()
    core.auth(authorization)
    if type(attempt_id) is not str or core.ID.fullmatch(attempt_id) is None:
        raise HTTPException(422, 'invalid_sandbox_attempt')
    try:
        with db() as conn:
            conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
            snapshot = core.read(conn, attempt_id)
            rows = conn.execute(
                'select sequence,stage,event_type,status,occurred_at,event_key,evidence_ids,payload '
                'from aiops.run_events where run_id=%s order by sequence',
                (snapshot['run_id'],)
            ).fetchall()
            value = project_journey(snapshot, rows, attempt_id)
        return JSONResponse(value, headers=core.HEADERS)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(503, 'sandbox_journey_unavailable') from None
