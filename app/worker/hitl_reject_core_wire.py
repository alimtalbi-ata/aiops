"""Worker-owned Core REJECT delivery wire preflight. NOT connected to runtime poller.

The caller injects a trusted async post(path, json_body) -> (status_code, dict).
This module never selects an HTTP origin, acquires a credential, opens a socket,
creates a Temporal client, or grants human/effect authorization. Core owns the
lease, tenant/run ownership, proposal hash/revision and delivered ACK.
"""
from datetime import datetime, timedelta, timezone
import re

from worker.hitl_reject_notification import (
    UnqualifiedNotification, notify_reject_batch, prepare_reject,
)

CORE_SCHEMA = "aiops.core-hitl-reject-delivery.v1"
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{1,127}\Z", re.ASCII)
_ACK_KEYS = frozenset((
    "owner", "run_id", "proposal_id", "proposal_hash", "proposal_revision",
    "lease_token", "execution_allowed", "effect_allowed",
))


def _valid_id(value):
    return type(value) is str and _ID.fullmatch(value) is not None


def _core_response(response, status_code):
    if (type(status_code) is not int or status_code != 200
            or type(response) is not dict
            or response.get("schema") != CORE_SCHEMA
            or response.get("execution_allowed") is not False
            or response.get("effect_allowed") is not False):
        raise UnqualifiedNotification("core_wire_unqualified")
    return response


def _validate_claim(response, tenant_id, owner, *, now=None):
    items = response.get("items")
    if type(items) is not list or len(items) > 1:
        raise UnqualifiedNotification("core_claim_batch_unqualified")
    if not items:
        if response.get("status") != "UNKNOWN":
            raise UnqualifiedNotification("core_empty_claim_status")
        return
    if response.get("status") != "LEASED":
        raise UnqualifiedNotification("core_claim_not_leased")
    if now is None:
        now = datetime.now(timezone.utc)
    if not isinstance(now, datetime) or now.tzinfo is None:
        raise UnqualifiedNotification("core_clock_unqualified")
    for item in items:
        if (type(item) is not dict
                or item.get("tenant_id") != tenant_id
                or item.get("lease_owner") != owner
                or (item.get("human_approved") is not None
                    and item.get("human_approved") is not False)):
            raise UnqualifiedNotification("core_claim_identity_unqualified")
        expiry = item.get("lease_until")
        if type(expiry) is not str:
            raise UnqualifiedNotification("core_lease_expiry_missing")
        try:
            lease_until = datetime.fromisoformat(expiry)
        except ValueError as exc:
            raise UnqualifiedNotification("core_lease_expiry_invalid") from exc
        if (lease_until.tzinfo is None
                or lease_until <= now + timedelta(seconds=1)):
            raise UnqualifiedNotification("core_lease_expired")
    # Reuse the existing fail-closed signal and ACK binding validator.
    prepare_reject(response, owner)


async def deliver_core_reject_once(*, tenant_id, owner, post, signal):
    """Single test-only claim -> Temporal notification -> Core ACK attempt.

    No polling, retries, real network transport, authorization or side effects.
    An ACK transport exception propagates; real network loss remains NOT_TESTED.
    """
    if not _valid_id(tenant_id) or not _valid_id(owner):
        raise UnqualifiedNotification("core_route_identity_invalid")
    root = f"/api/tenants/{tenant_id}/hitl/reject-delivery"
    status, response = await post(root + "/claim", {"owner": owner, "limit": 1})
    response = _core_response(response, status)
    _validate_claim(response, tenant_id, owner)

    async def acknowledge(event_id, request):
        if (not _valid_id(event_id) or request.get("tenant_id") != tenant_id
                or frozenset(request) != _ACK_KEYS | {"tenant_id"}
                or request.get("execution_allowed") is not False
                or request.get("effect_allowed") is not False):
            raise UnqualifiedNotification("core_ack_route_unqualified")
        # Core #250 requires EXACT eight keys: tenant is fenced by URL and
        # checked against the immutable claim before dropping from JSON body.
        body = {key: request[key] for key in _ACK_KEYS}
        code, receipt = await post(root + f"/{event_id}/ack", body)
        return _core_response(receipt, code)

    return await notify_reject_batch(
        response, owner=owner, signal=signal, acknowledge=acknowledge)
