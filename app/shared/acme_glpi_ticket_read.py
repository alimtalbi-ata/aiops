"""Optional read-only GLPI confirmation of the existing NOC/Core/Evidence join.

Consumes project_itsm_evidence() output; never treats a signed NOC claim as
GLPI verification. Requires a server-provided GLPI session and application
token, HTTPS, a 200 JSON Ticket read, and explicit matching incident/run link
fields in that GLPI record. Standard GLPI tickets may not contain these custom
fields: in that case the result intentionally stays UNKNOWN/null.

This module does not authenticate a user, create a GLPI session, or attest
runtime/tenant ACL. No POST, side effects, redirects, proxies or raw payloads.
"""
import json
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener
from shared.tenant_scope import reject_unqualified_tenant_scope

_TICKET = re.compile(r"[1-9][0-9]{0,17}\Z")
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\Z")
_SHA = re.compile(r"[a-f0-9]{64}\Z")
_SOURCE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z")
_MAX_BYTES = 65536


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _pairs_no_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _configured_origin(base_url):
    if not isinstance(base_url, str) or len(base_url) > 256:
        return None
    try:
        parsed = urlsplit(base_url)
        if (parsed.scheme != "https" or not parsed.hostname or parsed.username
                or parsed.password or parsed.query or parsed.fragment
                or parsed.path not in ("", "/") or not parsed.port in (None, 443)):
            return None
        # No credential, query, path, or attacker-controlled URL from a ticket.
        return "https://" + parsed.netloc.rstrip("/")
    except ValueError:
        return None


def _token(value):
    return (isinstance(value, str) and 16 <= len(value) <= 512
            and value.isascii() and not any(ch.isspace() for ch in value))


def _qualified_projection(value):
    """Require the existing Core ledger projection, not arbitrary joined IDs.

    These checks establish internal referential consistency only. A Core
    evidence reference is NOT an authenticated capture or a tenant ACL proof.
    """
    # The projector rejects nested tenant claims; enforce the same boundary
    # when this adapter receives a direct or altered projection. The one
    # top-level false flag is a declared non-attestation, not a scope claim.
    try:
        reject_unqualified_tenant_scope({
            key: item for key, item in value.items()
            if key != "tenant_acl_qualified"
        })
    except (ValueError, TypeError):
        return False
    if (value.get("schema") != "aiops.acme-itsm-evidence-link.v1"
            or value.get("state") != "CORRELATED_UNATTESTED"
            or value.get("classification") != "SYNTHETIC_ONLY"
            or value.get("evidence_source_contract") != "CORE_AI_LEDGER_INTERNAL_READ"
            or value.get("tenant_acl_qualified") is not False
            or value.get("runtime_attested") is not False
            or value.get("effect_applied") is not False
            or value.get("live_remediation_authorized") is not False):
        return False
    ids, refs = value.get("evidence_ids"), value.get("evidence_refs")
    if (not isinstance(ids, list) or not 1 <= len(ids) <= 80
            or not isinstance(refs, list) or len(refs) != len(ids)
            or any(not isinstance(x, str) or _ID.fullmatch(x) is None for x in ids)
            or len(set(ids)) != len(ids)):
        return False
    seen = set()
    for item in refs:
        if (not isinstance(item, dict)
                or set(item) != {"evidence_id", "source", "payload_sha256", "known_at"}
                or not isinstance(item["evidence_id"], str)
                or _ID.fullmatch(item["evidence_id"]) is None
                or not isinstance(item["source"], str)
                or _SOURCE.fullmatch(item["source"]) is None
                or not isinstance(item["payload_sha256"], str)
                or _SHA.fullmatch(item["payload_sha256"]) is None
                or not isinstance(item["known_at"], str)
                or not item["known_at"] or len(item["known_at"]) > 48
                or item["evidence_id"] in seen):
            return False
        try:
            known = datetime.fromisoformat(item["known_at"])
        except ValueError:
            return False
        if (known.tzinfo is None or known.utcoffset() is None
                or known.astimezone(timezone.utc) >
                datetime.now(timezone.utc) + timedelta(minutes=5)):
            return False
        seen.add(item["evidence_id"])
    return seen == set(ids)


def read_verified_glpi_link(correlation, *, base_url=None, session_token=None,
                            app_token=None, opener=None):
    """GET one claimed Ticket; fail closed on unavailable/ambiguous linkage.

    `opener` is injectable for offline HTTP mocks. In production, credentials
    must come from a server-side secret provider, never from browser input.
    The GLPI ticket must expose canonical `incident_id` and `run_id` fields;
    no inference from title, comments, or free text is permitted.
    """
    if not isinstance(correlation, dict):
        return {"state": "UNKNOWN", "ticket_id": None,
                "ticket_verification": "UNKNOWN"}
    result = dict(correlation)
    result["ticket_id"] = None
    result["ticket_verification"] = "UNKNOWN_NO_AUTHENTICATED_GLPI_LINK"
    if not _qualified_projection(result):
        # A malformed or forged projection cannot retain a correlated state.
        result.update(state="UNKNOWN", run_id=None, incident_id=None,
                      evidence_ids=[], evidence_refs=[], classification="UNKNOWN",
                      glpi_ticket_claim=None,
                      ticket_verification="UNKNOWN_INVALID_CORE_EVIDENCE_PROJECTION")
        return result
    claim = result.get("glpi_ticket_claim")
    run_id, incident_id = result.get("run_id"), result.get("incident_id")
    origin = _configured_origin(base_url)
    if (not isinstance(claim, str) or _TICKET.fullmatch(claim) is None
            or not isinstance(run_id, str) or _ID.fullmatch(run_id) is None
            or not isinstance(incident_id, str) or _ID.fullmatch(incident_id) is None
            or not origin or not _token(session_token) or not _token(app_token)):
        return result
    url = origin + "/apirest.php/Ticket/" + claim
    request = Request(url, method="GET", headers={
        "Session-Token": session_token, "App-Token": app_token,
        "Accept": "application/json", "Cache-Control": "no-store"})
    try:
        client = opener if opener is not None else build_opener(ProxyHandler({}), _NoRedirect())
        with client.open(request, timeout=4) as response:
            if response.status != 200 or response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower() != "application/json":
                return result
            raw = response.read(_MAX_BYTES + 1)
        if len(raw) > _MAX_BYTES:
            return result
        ticket = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs_no_duplicates)
        if not isinstance(ticket, dict):
            return result
        # A matching ID in an unqualified tenant-scoped ticket is not a
        # safe cross-system link. Reject nested/aliased claims as for Core.
        reject_unqualified_tenant_scope(ticket)
        ticket_id = ticket.get("id")
        if type(ticket_id) is int:
            ticket_id = str(ticket_id)
        if (ticket_id != claim or ticket.get("run_id") != run_id
                or ticket.get("incident_id") != incident_id
                or type(ticket.get("is_deleted")) is not int
                or ticket["is_deleted"] != 0):
            return result
    except (OSError, ValueError, UnicodeError, TypeError, AttributeError):
        return result
    result["ticket_id"] = claim
    result["ticket_verification"] = "GLPI_GET_200_EXPLICIT_LINK_MATCH_NO_TENANT_ATTESTATION"
    # Never promote the synthetic ledger or NOC to runtime/tenant attestation.
    result["runtime_attested"] = False
    result["tenant_acl_qualified"] = False
    return result
