"""Golden #802 f594d04e02abde19b2299fbb523bf9d0d0e360b8, historical offline predicates, no routes."""
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException
from .acme_historical_journey_offline import TENANT, SCENARIO, ISSUER, ident

def validate(x):
    if (x.tenant_id != TENANT or x.scenario_id != SCENARIO
            or x.mode != 'SIMULATION' or x.approval_issuer != ISSUER
            or x.idempotency_key != x.attempt_id
            or x.live_effects_allowed is not False):
        raise HTTPException(403, 'sandbox_scope_or_effect_denied')

def approval_fresh(issued, expires, *, now):
    """RG-ACME-19: validate once before I/O and again under PG16 terminal lock."""
    if (issued.tzinfo is None or expires.tzinfo is None
            or issued.utcoffset() != timedelta(0)
            or expires.utcoffset() != timedelta(0)
            or issued > now or expires <= now
            or expires <= issued or expires - issued > timedelta(minutes=5)):
        raise HTTPException(503, 'sandbox_twin_approval_stale_or_invalid')

def terminal_ticket_readback_bound(worker_doc, canonical_ticket):
    """Preserve immutable pre-RG-19 receipts, never relax NEW terminal admission.

    Historical Worker v1 receipts omitted ticket_id; their Core terminal row
    was already atomically committed and is append-only. All other persisted
    Run, ticket, source, digest, nonce and audit checks still apply in read().
    New Core resolve() always requires the explicit canonical ticket_id.
    An explicitly foreign or null ticket_id is never compatible.
    """
    return (type(worker_doc) is dict and
            ('ticket_id' not in worker_doc or
             worker_doc['ticket_id'] == canonical_ticket))

