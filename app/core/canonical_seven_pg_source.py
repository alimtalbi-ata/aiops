"""Core-owned, negative-only canonical seven-event PostgreSQL readback producer.

This is the source-side *SQL contract* for a separately authenticated HTTPS
service, not an HTTP server, IdP verifier or native GLPI authorization.
Call only with a fresh, dedicated read-only PG transaction after independent
service authentication. The disposable TLS harness exercises that boundary.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from core import actor_canonical_seven_source as binding


def read_canonical_seven(conn, request, *, source: str, issuer: str,
                         now: datetime) -> dict | None:
    """Return an exact synthetic source proof or None (UNKNOWN), never ALLOW.

    The caller must pin source and issuer in trusted server configuration.
    No caller-supplied tenant or ownership projection grants human GLPI rights.
    The transaction is made read-only *before* any query. No audit mutation.
    """
    if (not isinstance(request, dict) or set(request) != set(binding._SCOPE)
            or any(type(v) is not str or not v for v in request.values())
            or request["permission"] != "run:read"
            or type(source) is not str or not source
            or type(issuer) is not str or not issuer
            or not isinstance(now, datetime) or now.tzinfo is None):
        return None
    now = now.astimezone(timezone.utc)
    conn.execute("set transaction read only")
    grants = conn.execute(
        "select expires_at,revoked from public.ci_actor_source_grants "
        "where issuer=%s and actor_subject=%s and tenant_id=%s "
        "and run_id=%s and incident_id=%s and glpi_instance_id=%s "
        "and ticket_id=%s and glpi_entity_id=%s and permission=%s",
        (request["actor_issuer"], request["actor_subject"], request["tenant_id"],
         request["run_id"], request["incident_id"], request["glpi_instance_id"],
         request["ticket_id"], request["glpi_entity_id"], request["permission"])
    ).fetchall()
    if (len(grants) != 1 or grants[0][1] is not False
            or grants[0][0] <= now):
        return None
    linked = conn.execute(
        "select r.run_id,r.incident_id,i.synthetic from aiops.runs r "
        "join aiops.incidents i on i.incident_id=r.incident_id "
        "where r.run_id=%s and r.incident_id=%s and r.mode='DEMO'",
        (request["run_id"], request["incident_id"])).fetchone()
    if linked != (request["run_id"], request["incident_id"], True):
        return None
    required = (
        ("incident", request["incident_id"]),
        ("run", request["run_id"]),
        ("glpi_instance", request["glpi_instance_id"]),
        ("glpi_ticket", request["glpi_instance_id"] + ":" + request["ticket_id"]),
        ("glpi_entity", request["glpi_instance_id"] + ":" + request["glpi_entity_id"]),
    )
    owned = conn.execute(
        "select resource_kind,resource_id,tenant_id,verified,source_event_id,"
        "observed_at,known_at from aiops.tenant_resource_ownership "
        "where (resource_kind,resource_id) in "
        "((%s,%s),(%s,%s),(%s,%s),(%s,%s),(%s,%s))",
        tuple(value for pair in required for value in pair)).fetchall()
    if (len(owned) != len(required)
            or {(r[0], r[1]) for r in owned} != set(required)
            or any(r[2] != request["tenant_id"] or r[3] is not True
                   or not isinstance(r[4], str) or not r[4]
                   or not now - timedelta(minutes=5) <= r[5] <= r[6] <= now
                   for r in owned)):
        return None
    rows = conn.execute(
        "select e.external_id,e.evidence_id,e.payload_hash,e.payload,"
        "e.provenance,e.observed_at,e.known_at,r.event_id,r.sequence,"
        "r.stage,r.event_type,r.status,r.payload,r.evidence_ids "
        "from aiops.evidence e join aiops.run_events r "
        "on r.run_id=%s and r.payload->>'source_event_id'=e.external_id "
        "where e.source=%s and e.provenance->>'run_id'=%s "
        "order by r.sequence",
        (request["run_id"], source, request["run_id"])).fetchall()
    total = conn.execute(
        "select count(*) from aiops.run_events where run_id=%s",
        (request["run_id"],)).fetchone()[0]
    if len(rows) != 7 or total != 7:
        return None
    events, seen_ids, seen_evidence = [], set(), set()
    for pos, row in enumerate(rows, 1):
        (source_id, evidence_id, payload_hash, payload, provenance, observed,
         known, event_id, sequence, stage, event_type, status,
         run_payload, evidence_ids) = row
        if (type(sequence) is not int or sequence != pos
                or not isinstance(payload, dict) or payload != run_payload
                or evidence_ids != [evidence_id]
                or not isinstance(provenance, dict)
                or any(provenance.get(k) != request[k]
                       for k in ("tenant_id", "incident_id", "run_id"))
                or any(payload.get(k) != request[k]
                       for k in ("tenant_id", "incident_id", "run_id",
                                 "ticket_id", "glpi_entity_id"))
                or payload.get("source_event_id") != source_id
                or payload.get("sequence") != pos
                or source_id in seen_ids or evidence_id in seen_evidence
                or payload_hash != binding._digest(binding.PAYLOAD_DOMAIN, payload)
                or not now - timedelta(minutes=5) <= observed <= known <= now):
            return None
        seen_ids.add(source_id)
        seen_evidence.add(evidence_id)
        full = {
            "event_id": event_id, "run_id": request["run_id"],
            "incident_id": request["incident_id"],
            "tenant_id": request["tenant_id"], "sequence": sequence,
            "stage": stage, "event_type": event_type, "status": status,
            "evidence_id": evidence_id, "source_event_id": source_id,
            "source_payload_hash": payload_hash,
            "observed_at": int(observed.timestamp()),
            "known_at": int(known.timestamp()),
        }
        events.append({
            "sequence": sequence, "source_event_id": source_id,
            "evidence_id": evidence_id, "payload": payload,
            "payload_hash": payload_hash, "full_event": full,
            "full_event_hash": binding._digest(binding.FULL_DOMAIN, full),
        })
    return {
        **request, "schema": binding.SCHEMA, "issuer": issuer,
        "source_system": "CORE_CANONICAL_READBACK",
        "observed_at": int(rows[0][5].timestamp()),
        "known_at": int(rows[-1][6].timestamp()),
        "expires_at": int(min(grants[0][0], now + timedelta(seconds=60)).timestamp()),
        "revoked": False, "events": events,
    }


def read_core_written_seven(conn, request, *, source: str, issuer: str,
                            now: datetime) -> dict | None:
    """Read seven *Core API-written* SYN-EVT keys, not fixture-inserted events.

    Requires the independently service-authenticated caller to pin the source
    and source issuer. The synthetic actor grant is a negative-only source
    ownership check, NOT independently qualified IdP/GLPI human permission.
    The original SQL producer checks the exact Incident/Run, five ownership
    rows, grant freshness/revocation, seven Evidence and both hash domains.
    This additional bridge requires 015 event_key and exact actor provenance.
    """
    proof = read_canonical_seven(conn, request, source=source,
                                 issuer=issuer, now=now)
    if proof is None:
        return None
    rows = conn.execute(
        "select r.sequence,r.event_key,r.stage,r.event_type,r.status,"
        "r.payload,e.provenance from aiops.run_events r "
        "join aiops.evidence e on e.evidence_id=r.evidence_ids->>0 "
        "where r.run_id=%s order by r.sequence",
        (request["run_id"],)
    ).fetchall()
    if len(rows) != 7:
        return None
    for pos, row in enumerate(rows, 1):
        sequence, key, stage, event_type, status, payload, provenance = row
        expected_key = f"SYN-EVT-{pos:02d}"
        if (sequence != pos or key != expected_key
                or stage != "INGEST" or event_type != "SYNTHETIC_SOURCE_EVENT"
                or status != "PASS"
                or not isinstance(payload, dict)
                or not isinstance(provenance, dict)
                or payload.get("source_event_id") != key
                or payload.get("actor_subject") != request["actor_subject"]
                or payload.get("actor_issuer") != request["actor_issuer"]
                or payload.get("source_issuer") != issuer
                or payload.get("synthetic") is not True
                or any(provenance.get(k) != request[k] for k in (
                    "tenant_id", "incident_id", "run_id",
                    "actor_subject", "actor_issuer"))
                or provenance.get("source_issuer") != issuer
                or proof["events"][pos - 1]["source_event_id"] != key):
            return None
    # The caller must not promote this source proof into human ALLOW/VERIFIED.
    return proof
