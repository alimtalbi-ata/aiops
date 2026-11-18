"""Fail-closed Worker-side HITL REJECT notification contract (not wired to Core).

A Temporal signal is only an at-least-once notification. The authoritative
proposal, lease and decision checks belong to Core. Until Core provides the
tenant/owner/hash/revision-fenced claim and ACK projection, this module must
NOT be attached to the production Worker poller. No APPROVE path exists.
"""
import re

_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


class UnqualifiedNotification(ValueError):
    """A Core claim or delivery ACK is insufficiently fenced."""


def _nonempty(value):
    return type(value) is str and bool(value.strip())


def _no_effect(value):
    return (isinstance(value, dict)
            and value.get("execution_allowed") is False
            and value.get("effect_allowed") is False)


def prepare_reject(snapshot, owner):
    """Validate one claimed batch atomically before any Temporal signal.

    tenant_id and lease_owner are required from a future Core-owned claim
    projection. The currently installed SQL-model/011 does not prove these.
    """
    if not _nonempty(owner) or not _no_effect(snapshot):
        raise UnqualifiedNotification("claim_not_no_effect")
    items = snapshot.get("items")
    if type(items) is not list:
        raise UnqualifiedNotification("claim_items_invalid")
    prepared = []
    seen = set()
    for item in items:
        if not _no_effect(item):
            raise UnqualifiedNotification("item_not_no_effect")
        fields = ("event_id", "tenant_id", "run_id", "proposal_id",
                  "proposal_hash", "lease_token", "lease_owner")
        if any(not _nonempty(item.get(k)) for k in fields):
            raise UnqualifiedNotification("item_binding_missing")
        if (item["lease_owner"] != owner
                or not _SHA256.fullmatch(item["proposal_hash"])
                or type(item.get("proposal_revision")) is not int
                or item["proposal_revision"] < 1
                or item.get("decision") != "REJECT"
                or item.get("source_status") not in ("REJECTED", "REVOKED")
                or item.get("human_approved") is True
                or item["event_id"] in seen):
            raise UnqualifiedNotification("item_binding_unqualified")
        seen.add(item["event_id"])
        signal = {
            "event_id": item["event_id"],
            "tenant_id": item["tenant_id"],
            "run_id": item["run_id"],
            "proposal_id": item["proposal_id"],
            "proposal_hash": item["proposal_hash"],
            "proposal_revision": item["proposal_revision"],
            "decision": "REJECT",
            "source_status": item["source_status"],
            "notification_only": True,
            "execution_allowed": False,
            "effect_allowed": False,
        }
        ack = {
            "owner": owner,
            "tenant_id": item["tenant_id"],
            "run_id": item["run_id"],
            "proposal_id": item["proposal_id"],
            "proposal_hash": item["proposal_hash"],
            "proposal_revision": item["proposal_revision"],
            "lease_token": item["lease_token"],
            "execution_allowed": False,
            "effect_allowed": False,
        }
        prepared.append((item["event_id"], item["run_id"], signal, ack))
    return prepared


def verify_delivery_ack(receipt, event_id, request):
    """An ACK must match the claimed immutable binding, not merely HTTP 200."""
    if (not _no_effect(receipt)
            or receipt.get("event_id") != event_id
            or receipt.get("status") != "DELIVERED"
            or type(receipt.get("idempotent")) is not bool
            or any(receipt.get(key) != request[key] for key in
                   ("tenant_id", "run_id", "proposal_id", "proposal_hash",
                    "proposal_revision", "owner"))):
        raise UnqualifiedNotification("ack_binding_unqualified")
    return {
        "event_id": event_id,
        "status": "DELIVERED",
        "idempotent": receipt["idempotent"],
        "execution_allowed": False,
        "effect_allowed": False,
    }


async def notify_reject_batch(snapshot, *, owner, signal, acknowledge):
    """Inject transport functions; never fetch Core or create Temporal clients.

    signal(run_id, payload) and acknowledge(event_id, request) are async.
    An exception during signal leaves the lease unACKed. If ACK response is
    lost after Core commit, only Core can prove idempotency on retry.
    """
    prepared = prepare_reject(snapshot, owner)
    receipts = []
    for event_id, run_id, payload, ack_request in prepared:
        await signal(run_id, payload)
        receipt = await acknowledge(event_id, ack_request)
        receipts.append(verify_delivery_ack(receipt, event_id, ack_request))
    return receipts
