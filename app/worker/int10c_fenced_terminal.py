"""Distinct #234 terminal_reject adapter; no runtime registration or transport.
Core alone owns expiry, permission, current token and durable receipt checks.
"""
import re
from datetime import datetime
from worker.hitl_reject_core_wire import _ACK_KEYS, _valid_id, _core_response
from worker.hitl_reject_terminal_runtime import RECEIPT_SCHEMA, UnqualifiedTerminal

_HASH = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)
_TOKEN = re.compile(r"[A-Za-z0-9_-]{32,128}\Z", re.ASCII)
_REPLY = frozenset(("schema", "status", "receipt_schema", "event_id", "tenant_id",
                    "run_id", "proposal_id", "proposal_hash", "proposal_revision",
                    "actor_id", "attempts", "dead_at", "receipt_sha256", "idempotent",
                    "execution_allowed", "effect_allowed"))

async def recover_fenced_terminal(tenant_id, event_id, payload, *, terminal):
    """terminal(tenant_id,event_id,body) -> (HTTP status, decoded dict).
    Caller provides trusted callback; no credentials or tokens returned.
    Replay uses the same original body, never a replacement token.
    """
    if (not _valid_id(tenant_id) or not _valid_id(event_id)
            or type(payload) is not dict or frozenset(payload) != _ACK_KEYS
            or not all(_valid_id(payload[k]) for k in ("owner", "run_id", "proposal_id"))
            or type(payload["proposal_hash"]) is not str or not _HASH.fullmatch(payload["proposal_hash"])
            or type(payload["lease_token"]) is not str or not _TOKEN.fullmatch(payload["lease_token"])
            or type(payload["proposal_revision"]) is not int or payload["proposal_revision"] < 1
            or payload["execution_allowed"] is not False or payload["effect_allowed"] is not False):
        raise UnqualifiedTerminal("terminal_request_unqualified")
    body = dict(payload)
    try:
        status, reply = await terminal(tenant_id, event_id, dict(body))
        _core_response(reply, status)
        if (frozenset(reply) != _REPLY or reply["status"] != "DEAD"
                or reply["receipt_schema"] != RECEIPT_SCHEMA
                or reply["tenant_id"] != tenant_id or reply["event_id"] != event_id
                or reply["actor_id"] != body["owner"]
                or any(reply[k] != body[k] for k in ("run_id", "proposal_id", "proposal_hash", "proposal_revision"))
                or type(reply["proposal_revision"]) is not int
                or type(reply["attempts"]) is not int or reply["attempts"] < 8
                or type(reply["idempotent"]) is not bool
                or type(reply["receipt_sha256"]) is not str or not _HASH.fullmatch(reply["receipt_sha256"])
                or type(reply["dead_at"]) is not str
                or datetime.fromisoformat(reply["dead_at"]).utcoffset() is None):
            raise ValueError("terminal_receipt_unqualified")
    except Exception:
        raise UnqualifiedTerminal("terminal_core_unqualified") from None
    return dict(reply)
