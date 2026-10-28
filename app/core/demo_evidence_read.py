"""Internal, read-only evidence-reference qualification for synthetic Demo ledger.

This is NOT tenant RBAC or a live evidence attestation. Missing or unqualified
sources are UNKNOWN; the endpoint never returns raw evidence payloads.
"""
import json
import re
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Header, HTTPException
from shared.tenant_scope import reject_unqualified_tenant_scope

router = APIRouter()
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\Z")
_SHA = re.compile(r"[a-f0-9]{64}\Z")
_SOURCE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z")
_MODES = frozenset(("DEMO", "REPLAY", "STORY"))


def _unknown():
    raise HTTPException(503, "evidence_references_unqualified")


def _ids(value):
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (TypeError, ValueError):
            _unknown()
    if not isinstance(value, list) or len(value) > 80:
        _unknown()
    if any(not isinstance(v, str) or not _ID.fullmatch(v) for v in value):
        _unknown()
    if len(set(value)) != len(value):
        _unknown()
    return set(value)


def register_demo_evidence_routes(app, db, auth, bearer):
    @router.get("/api/noc/runs/{rid}/evidence-refs")
    def evidence_refs(rid: str, authorization: str | None = Header(default=None)):
        auth(bearer(authorization))  # 401 before any database access
        if not _ID.fullmatch(rid):
            _unknown()
        with db() as conn:
            run = conn.execute("select mode from aiops.runs where run_id=%s", (rid,)).fetchone()
            if not run or run[0] not in _MODES:
                _unknown()
            analyses = conn.execute(
                "select evidence_ids from aiops.analysis_records where run_id=%s", (rid,)
            ).fetchall()
            critiques = conn.execute(
                "select evidence_ids from aiops.critique_records where run_id=%s", (rid,)
            ).fetchall()
            if not analyses or not critiques or len(analyses) > 50 or len(critiques) > 50:
                _unknown()
            analysis_ids = set().union(*(_ids(row[0]) for row in analyses))
            critique_ids = set().union(*(_ids(row[0]) for row in critiques))
            if not analysis_ids or len(analysis_ids) > 80 or analysis_ids != critique_ids:
                _unknown()
            rows = conn.execute(
                """select e.evidence_id,e.source,e.payload_hash,e.observed_at,
                          e.known_at,e.provenance
                   from aiops.evidence e
                   where e.evidence_id=any(%s) and exists (
                       select 1 from aiops.run_events ev
                       where ev.run_id=%s
                         and ev.evidence_ids @> jsonb_build_array(e.evidence_id)
                   )
                   order by e.evidence_id limit 81""",
                (sorted(analysis_ids), rid),
            ).fetchall()
        if len(rows) != len(analysis_ids):
            _unknown()
        items = []
        for evidence_id, source, digest, observed_at, known_at, provenance in rows:
            if isinstance(provenance, str):
                try:
                    provenance = json.loads(provenance)
                except (TypeError, ValueError):
                    _unknown()
            try:
                reject_unqualified_tenant_scope(provenance)
            except ValueError:
                _unknown()
            if (not isinstance(provenance, dict)
                    or provenance.get("synthetic") is not True
                    or provenance.get("observed") is not False
                    or provenance.get("run_id") != rid
                    or not isinstance(source, str) or not _SOURCE.fullmatch(source)
                    or not isinstance(digest, str) or not _SHA.fullmatch(digest)
                    or not isinstance(known_at, datetime)
                    or known_at.tzinfo is None or known_at.utcoffset() is None
                    or known_at.astimezone(timezone.utc) > datetime.now(timezone.utc) + timedelta(minutes=5)
                    or observed_at is not None):
                _unknown()
            items.append({"evidence_id": evidence_id, "source": source,
                          "payload_sha256": digest, "known_at": known_at.isoformat()})
        return {"schema": "aiops.core-demo-evidence-refs.v1",
                "run_id": rid, "classification": "SYNTHETIC_ONLY",
                "tenant_acl_qualified": False, "runtime_attested": False,
                "event_link_verified": True, "items": items}

    app.include_router(router)
