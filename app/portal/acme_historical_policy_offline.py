"""Golden #802 f594d04e02abde19b2299fbb523bf9d0d0e360b8, historical join only, not independent decision."""
import hashlib, hmac, json, re
from fastapi import HTTPException
from .acme_historical_journey_offline import TENANT, ISSUER

def qualify(attempt, core, twin, *, historical=False):
    expected_status = 'RESOLVED' if historical else 'PREPARED'
    ids = ('incident_id', 'run_id', 'ticket_id', 'proposal_id')
    if (any(doc.get('attempt_id') != attempt or doc.get('tenant_id') != TENANT
            for doc in (core, twin))
            or any(not isinstance(core.get(k), str) or not core[k]
                   or core[k] != twin.get(k) for k in ids)
            or not core['ticket_id'].startswith('SIM-GLPI-')
            or core.get('incident_status') != expected_status
            or core.get('run_status') != core.get('incident_status')
            or core.get('ticket_status') != expected_status
            or core.get('ticket_authority') != 'SIMULATED_ONLY'
            or core.get('glpi_mode') != 'SIMULATED_ONLY'
            or type(core.get('source_event_count')) is not int
            or core.get('source_event_count') != 7
            or core.get('source_hashes_qualified') is not True
            or core.get('analysis_validated') is not True
            or core.get('critic_validated') is not True
            or type(core.get('evidence_count')) is not int
            or core['evidence_count'] < 2
            or twin.get('approval_issuer') != ISSUER
            or twin.get('issuer_id') != 'twin-acme-test'
            or twin.get('approval_kind') != 'SIMULATED'
            or twin.get('approval_status') != 'SIMULATED'
            or twin.get('approval_phase') != 'PRE_RESOLUTION'
            or twin.get('core_status_at_issuance') != 'PREPARED'
            or twin.get('core_request_sha256') != core.get('request_sha256')
            or twin.get('core_source_event_ids') != core.get('source_event_ids')
            or not isinstance(twin.get('approval_id'), str)
            or not twin['approval_id'].startswith('SIM-APP-')
            or any(doc.get(k) is not False for doc in (core, twin)
                   for k in ('human_approved', 'execution_allowed',
                             'effect_allowed', 'live_effects_allowed',
                             'real_glpi_writes_allowed'))):
        raise HTTPException(503, 'sandbox_policy_join_unqualified')
    if historical:
        # RG-ACME-24: read-only replay of a persisted simulated decision,
        # never an approval or new Policy evaluation after Core RESOLVED.
        worker_sha = core.get('worker_receipt_sha256')
        ticket_sha = core.get('terminal_ticket_sha256')
        if (core.get('source') != 'SYNTHETIC_SIMULATOR'
                or core.get('approval_id') != twin.get('approval_id')
                or core.get('worker_receipt_verified') is not True
                or core.get('terminal_ticket_receipt_verified') is not True
                or core.get('resolution_after_worker_receipt') is not True
                or core.get('approval_fresh_at_resolution') is not True
                or core.get('approval_nonce_consumed') is not True
                or core.get('approval_nonce_revoked') is not False
                or not isinstance(worker_sha, str)
                or not re.fullmatch(r'[a-f0-9]{64}', worker_sha)
                or not isinstance(ticket_sha, str)
                or not re.fullmatch(r'[a-f0-9]{64}', ticket_sha)):
            raise HTTPException(503, 'sandbox_historical_receipts_unqualified')
        binding = {
            'schema': 'aiops.portal.sim-glpi-ticket-digest.v1',
            'tenant_id': TENANT, 'attempt_id': attempt,
            'incident_id': core['incident_id'], 'run_id': core['run_id'],
            'ticket_id': core['ticket_id'], 'ticket_status': 'RESOLVED',
            'core_request_sha256': core.get('request_sha256'),
            'worker_receipt_sha256': worker_sha}
        expected_sha = hashlib.sha256(json.dumps(
            binding, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        if not hmac.compare_digest(ticket_sha, expected_sha):
            raise HTTPException(503, 'sandbox_historical_ticket_digest_mismatch')
    return ids

