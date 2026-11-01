"""Core-owned REJECT-only HITL outbox claim/ACK, using installed 011 ledger.

No approval, execution or Temporal call. A lease is an at-least-once
notification fence, not permission to remediate. Caller-supplied tenant/owner
and proposal fields are never themselves authorization.
"""
from __future__ import annotations

import re
import secrets
from datetime import datetime, timezone
from fastapi import APIRouter, Header
from fastapi.responses import JSONResponse
router = APIRouter()


def _x():
    # Lazy dependency avoids a cycle when PG16 tests import this module first.
    from core import itsm_xref
    return itsm_xref
SCHEMA = "aiops.core-hitl-reject-delivery.v1"
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{1,127}\Z", re.ASCII)
_HASH = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)
_TOKEN = re.compile(r"[A-Za-z0-9_-]{32,128}\Z", re.ASCII)
_HEADERS = {"Cache-Control": "no-store", "Pragma": "no-cache",
            "X-Content-Type-Options": "nosniff"}


def _response(code=200, **fields):
    headers = dict(_HEADERS)
    if code == 401:
        headers["WWW-Authenticate"] = "Bearer"
    return JSONResponse({"schema": SCHEMA, "status": "UNKNOWN",
                         "execution_allowed": False, "effect_allowed": False,
                         **fields}, status_code=code, headers=headers)


def _valid(value, pattern=_ID):
    return type(value) is str and pattern.fullmatch(value) is not None


def _authorized(header, tenant):
    actor, code = _x()._auth(header)
    if code != 200:
        return None, _response(code)
    if ("hitl:reject:deliver" not in actor["permissions"]
            or tenant not in actor["tenant_ids"]):
        return None, _response(403)
    return actor, None


def _proof(row, tenant):
    # Independent Core ownership attestation, not a client tenant header.
    kind, resource, owner_tenant, verified, source_id, observed, known = row
    if (kind != "run" or owner_tenant != tenant or verified is not True
            or not _valid(resource) or not _valid(source_id)
            or not isinstance(observed, datetime)
            or not isinstance(known, datetime)
            or observed.tzinfo is None or known.tzinfo is None):
        return False
    now = datetime.now(timezone.utc)
    if not (observed <= known <= now and (now - observed).total_seconds() <= 300):
        return False
    return _x()._owners_attested([row])


_CLAIM_SQL = """
select o.event_id,o.proposal_id,o.run_id,o.proposal_hash,o.proposal_revision,
       o.source_status,own.resource_kind,own.resource_id,own.tenant_id,
       own.verified,own.source_event_id,own.observed_at,own.known_at
from aiops.hitl_decision_outbox o
join aiops.action_proposals p on p.proposal_id=o.proposal_id
  and p.run_id=o.run_id and p.proposal_hash=o.proposal_hash
  and p.proposal_revision=o.proposal_revision
join aiops.approval_records a on a.approval_id=o.approval_id
  and a.proposal_id=o.proposal_id and a.proposal_hash=o.proposal_hash
join aiops.runs r on r.run_id=o.run_id and r.incident_id is not null
join aiops.tenant_resource_ownership own on own.resource_kind='run'
  and own.resource_id=o.run_id and own.tenant_id=%s
where o.decision='REJECT' and o.source_status in ('REJECTED','REVOKED')
  and ((o.source_status='REJECTED' and p.status='REJECTED' and a.decision='REJECT')
       or (o.source_status='REVOKED' and p.status='REVOKED' and a.decision='REVOKE'))
  and o.attempts < 8 and o.available_at <= statement_timestamp()
  and (o.status='PENDING' or
       (o.status='LEASED' and o.lease_until < statement_timestamp()))
order by o.created_at,o.event_id limit 1 for update of o skip locked
"""
_LEASE_SQL = """
update aiops.hitl_decision_outbox
set status='LEASED',lease_owner=%s,lease_token=%s,
    lease_until=statement_timestamp()+interval '30 seconds',attempts=attempts+1
where event_id=%s and decision='REJECT' and status in ('PENDING','LEASED')
returning lease_until
"""
_ACK_SQL = """
select o.status,o.lease_owner,o.lease_token,o.lease_until,o.proposal_id,
       o.run_id,o.proposal_hash,o.proposal_revision,o.decision,
       o.source_status,own.resource_kind,own.resource_id,own.tenant_id,
       own.verified,own.source_event_id,own.observed_at,own.known_at
from aiops.hitl_decision_outbox o
join aiops.action_proposals p on p.proposal_id=o.proposal_id
  and p.run_id=o.run_id and p.proposal_hash=o.proposal_hash
  and p.proposal_revision=o.proposal_revision
join aiops.approval_records a on a.approval_id=o.approval_id
  and a.proposal_id=o.proposal_id and a.proposal_hash=o.proposal_hash
join aiops.tenant_resource_ownership own on own.resource_kind='run'
  and own.resource_id=o.run_id and own.tenant_id=%s
where o.event_id=%s and o.decision='REJECT'
  and ((o.source_status='REJECTED' and p.status='REJECTED' and a.decision='REJECT')
       or (o.source_status='REVOKED' and p.status='REVOKED' and a.decision='REVOKE'))
for update of o
"""
_DELIVER_SQL = """
update aiops.hitl_decision_outbox
set status='DELIVERED',delivered_at=statement_timestamp()
where event_id=%s and status='LEASED' and lease_owner=%s
  and lease_token=%s and lease_until>statement_timestamp()
returning event_id
"""


@router.post("/api/tenants/{tenant_id}/hitl/reject-delivery/claim")
def claim_reject(tenant_id: str, payload: dict,
                 authorization: str | None = Header(default=None)):
    actor, denial = _authorized(authorization, tenant_id)
    if denial is not None:
        return denial
    if (not _valid(tenant_id) or type(payload) is not dict
            or set(payload) != {"owner", "limit"}
            or payload["owner"] != actor["actor_id"]
            or type(payload["limit"]) is not int or payload["limit"] != 1):
        return _response()
    try:
        with _x().db() as c:
            row = c.execute(_CLAIM_SQL, (tenant_id,)).fetchone()
            if row is None:
                return _response(items=[])
            (event_id, proposal_id, run_id, proposal_hash, revision,
             source_status, *ownership) = row
            if (not all(_valid(v) for v in (event_id, proposal_id, run_id))
                    or not _valid(proposal_hash, _HASH)
                    or type(revision) is not int or revision < 1
                    or source_status not in ("REJECTED", "REVOKED")
                    or not _proof(tuple(ownership), tenant_id)
                    or ownership[1] != run_id):
                return _response()
            token = secrets.token_urlsafe(32)
            lease = c.execute(_LEASE_SQL, (actor["actor_id"], token, event_id)).fetchone()
            if not lease or not isinstance(lease[0], datetime):
                return _response()
        return _response(status="LEASED", items=[{
            "event_id": event_id, "tenant_id": tenant_id, "run_id": run_id,
            "proposal_id": proposal_id, "proposal_hash": proposal_hash,
            "proposal_revision": revision, "decision": "REJECT",
            "source_status": source_status, "lease_owner": actor["actor_id"],
            "lease_token": token, "lease_until": lease[0].isoformat(),
            "execution_allowed": False, "effect_allowed": False,
        }])
    except Exception:
        return _response(503)


@router.post("/api/tenants/{tenant_id}/hitl/reject-delivery/{event_id}/ack")
def ack_reject(tenant_id: str, event_id: str, payload: dict,
               authorization: str | None = Header(default=None)):
    actor, denial = _authorized(authorization, tenant_id)
    if denial is not None:
        return denial
    required = {"owner", "run_id", "proposal_id", "proposal_hash",
                "proposal_revision", "lease_token", "execution_allowed", "effect_allowed"}
    if (not _valid(tenant_id) or not _valid(event_id)
            or type(payload) is not dict or set(payload) != required
            or payload["owner"] != actor["actor_id"]
            or not all(_valid(payload[k]) for k in ("run_id", "proposal_id"))
            or not _valid(payload["proposal_hash"], _HASH)
            or not _valid(payload["lease_token"], _TOKEN)
            or type(payload["proposal_revision"]) is not int
            or payload["proposal_revision"] < 1
            or payload["execution_allowed"] is not False
            or payload["effect_allowed"] is not False):
        return _response()
    try:
        with _x().db() as c:
            row = c.execute(_ACK_SQL, (tenant_id, event_id)).fetchone()
            if row is None:
                return _response()
            (status, owner, token, expiry, proposal_id, run_id, proposal_hash,
             revision, decision, source_status, *ownership) = row
            if (owner != actor["actor_id"] or token != payload["lease_token"]
                    or proposal_id != payload["proposal_id"]
                    or run_id != payload["run_id"]
                    or proposal_hash != payload["proposal_hash"]
                    or revision != payload["proposal_revision"]
                    or decision != "REJECT"
                    or source_status not in ("REJECTED", "REVOKED")
                    or ownership[1] != run_id or not _proof(tuple(ownership), tenant_id)):
                return _response()
            if status == "DELIVERED":
                return _response(status="DELIVERED", event_id=event_id,
                                 tenant_id=tenant_id, run_id=run_id,
                                 proposal_id=proposal_id, proposal_hash=proposal_hash,
                                 proposal_revision=revision, owner=owner, idempotent=True)
            if (status != "LEASED" or not isinstance(expiry, datetime)
                    or expiry.tzinfo is None or expiry <= datetime.now(timezone.utc)):
                return _response()
            delivered = c.execute(_DELIVER_SQL, (event_id, owner, token)).fetchone()
            if not delivered:
                return _response()
        return _response(status="DELIVERED", event_id=event_id,
                         tenant_id=tenant_id, run_id=run_id,
                         proposal_id=proposal_id, proposal_hash=proposal_hash,
                         proposal_revision=revision, owner=owner, idempotent=False)
    except Exception:
        return _response(503)


# Terminal REJECT is a separate Core-only, negative-effect transition. Worker
# must never infer DEAD from attempts=8 or mutate SQL directly.
TERMINAL_SCHEMA = "aiops.core-hitl-reject-terminal-receipt.v1"
_TERMINAL_SQL = """
select o.status,o.attempts,o.lease_owner,o.lease_token,o.lease_until,
       o.proposal_id,o.run_id,o.proposal_hash,o.proposal_revision,o.source_status,
       own.resource_kind,own.resource_id,own.tenant_id,own.verified,
       own.source_event_id,own.observed_at,own.known_at
from aiops.hitl_decision_outbox o
join aiops.action_proposals p on p.proposal_id=o.proposal_id
  and p.run_id=o.run_id and p.proposal_hash=o.proposal_hash
  and p.proposal_revision=o.proposal_revision
join aiops.approval_records a on a.approval_id=o.approval_id
  and a.proposal_id=o.proposal_id and a.proposal_hash=o.proposal_hash
join aiops.runs r on r.run_id=o.run_id and r.incident_id is not null
join aiops.tenant_resource_ownership own on own.resource_kind='run'
  and own.resource_id=o.run_id and own.tenant_id=%s
where o.event_id=%s and o.decision='REJECT'
  and ((o.source_status='REJECTED' and p.status='REJECTED' and a.decision='REJECT')
       or (o.source_status='REVOKED' and p.status='REVOKED' and a.decision='REVOKE'))
for update of o
"""
_TERMINAL_UPDATE_SQL = """
update aiops.hitl_decision_outbox
set status='DEAD',last_error='lease_attempt_budget_exhausted'
where event_id=%s and status='LEASED' and attempts>=8
  and lease_owner=%s and lease_token=%s
  and lease_until<=statement_timestamp() and decision='REJECT'
returning status,attempts,lease_until,statement_timestamp()
"""
_TERMINAL_INSERT_SQL = """
insert into aiops.hitl_reject_terminal_receipts
(event_id,tenant_id,run_id,proposal_id,proposal_hash,proposal_revision,
 actor_id,lease_owner,lease_token_sha256,attempts,lease_expired_at,dead_at,
 receipt_payload,receipt_sha256)
values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s)
"""
_TERMINAL_READ_SQL = """
select receipt_payload,receipt_sha256 from aiops.hitl_reject_terminal_receipts
where event_id=%s and tenant_id=%s and run_id=%s
"""
_TERMINAL_KEYS = {"owner", "run_id", "proposal_id", "proposal_hash",
                  "proposal_revision", "lease_token", "execution_allowed",
                  "effect_allowed"}


def _terminal_digest(value):
    import hashlib
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _terminal_json(value):
    import json
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _terminal_reply(receipt, digest, *, idempotent):
    # Raw lease tokens, token hashes, bearer credentials and approval identity
    # are deliberately excluded from the response.
    return _response(status="DEAD", receipt_schema=TERMINAL_SCHEMA,
                     event_id=receipt["event_id"], tenant_id=receipt["tenant_id"],
                     run_id=receipt["run_id"], proposal_id=receipt["proposal_id"],
                     proposal_hash=receipt["proposal_hash"],
                     proposal_revision=receipt["proposal_revision"],
                     actor_id=receipt["actor_id"], attempts=receipt["attempts"],
                     dead_at=receipt["dead_at"], receipt_sha256=digest,
                     idempotent=idempotent)


@router.post("/api/tenants/{tenant_id}/hitl/reject-delivery/{event_id}/dead")
def terminal_reject(tenant_id: str, event_id: str, payload: dict,
                    authorization: str | None = Header(default=None)):
    """Atomically exhaust one expired eighth REJECT lease and append audit.

    Requires a distinct service permission in addition to delivery permission.
    Every error is non-enumerating; no terminal success grants human authority.
    """
    actor, denial = _authorized(authorization, tenant_id)
    if denial is not None:
        return denial
    if "hitl:reject:terminal" not in actor["permissions"]:
        return _response(403)
    if (not _valid(tenant_id) or not _valid(event_id)
            or type(payload) is not dict or set(payload) != _TERMINAL_KEYS
            or payload["owner"] != actor["actor_id"]
            or not all(_valid(payload[k]) for k in ("run_id", "proposal_id"))
            or not _valid(payload["proposal_hash"], _HASH)
            or not _valid(payload["lease_token"], _TOKEN)
            or type(payload["proposal_revision"]) is not int
            or payload["proposal_revision"] < 1
            or payload["execution_allowed"] is not False
            or payload["effect_allowed"] is not False):
        return _response()
    try:
        with _x().db() as c:
            row = c.execute(_TERMINAL_SQL, (tenant_id, event_id)).fetchone()
            if row is None:
                return _response()
            (status, attempts, owner, token, expiry, proposal_id, run_id,
             proposal_hash, revision, source_status, *ownership) = row
            if (status not in ("LEASED", "DEAD")
                    or type(attempts) is not int or attempts < 8
                    or owner != actor["actor_id"]
                    or not isinstance(token, str)
                    or not secrets.compare_digest(token, payload["lease_token"])
                    or proposal_id != payload["proposal_id"]
                    or run_id != payload["run_id"]
                    or proposal_hash != payload["proposal_hash"]
                    or revision != payload["proposal_revision"]
                    or source_status not in ("REJECTED", "REVOKED")
                    or ownership[1] != run_id
                    or not _proof(tuple(ownership), tenant_id)
                    or not isinstance(expiry, datetime)
                    or expiry.tzinfo is None
                    or expiry > datetime.now(timezone.utc)):
                return _response()
            if status == "DEAD":
                found = c.execute(_TERMINAL_READ_SQL,
                                  (event_id, tenant_id, run_id)).fetchone()
                if not found:
                    return _response(503)
                receipt, digest = found
                if (not isinstance(receipt, dict)
                        or receipt.get("schema") != TERMINAL_SCHEMA
                        or receipt.get("actor_id") != actor["actor_id"]
                        or receipt.get("lease_owner") != owner
                        or receipt.get("lease_token_sha256") != _terminal_digest(token)
                        or receipt.get("proposal_hash") != proposal_hash
                        or receipt.get("proposal_revision") != revision
                        or not secrets.compare_digest(
                            str(digest), _terminal_digest(_terminal_json(receipt)))):
                    return _response(503)
                return _terminal_reply(receipt, digest, idempotent=True)
            changed = c.execute(_TERMINAL_UPDATE_SQL,
                                (event_id, owner, token)).fetchone()
            if not changed or changed[0] != "DEAD":
                return _response()
            _, committed_attempts, lease_until, dead_at = changed
            receipt = {
                "schema": TERMINAL_SCHEMA, "event_id": event_id,
                "tenant_id": tenant_id, "run_id": run_id,
                "proposal_id": proposal_id, "proposal_hash": proposal_hash,
                "proposal_revision": revision, "actor_id": actor["actor_id"],
                "lease_owner": owner, "lease_token_sha256": _terminal_digest(token),
                "attempts": committed_attempts, "source_status": source_status,
                "lease_expired_at": lease_until.isoformat(),
                "dead_at": dead_at.isoformat(), "decision": "REJECT",
                "execution_allowed": False, "effect_allowed": False,
                "human_glpi_authorization": "UNKNOWN"
            }
            digest = _terminal_digest(_terminal_json(receipt))
            c.execute(_TERMINAL_INSERT_SQL,
                      (event_id, tenant_id, run_id, proposal_id, proposal_hash,
                       revision, actor["actor_id"], owner, _terminal_digest(token),
                       committed_attempts, lease_until, dead_at,
                       _terminal_json(receipt), digest))
        return _terminal_reply(receipt, digest, idempotent=False)
    except Exception:
        return _response(503)
