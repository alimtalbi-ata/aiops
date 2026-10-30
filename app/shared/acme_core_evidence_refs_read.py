"""Optional authenticated Core Evidence *reference* read for ACME demo runs.

Reads the existing Core /api/noc/runs/{rid}/evidence-refs endpoint only.
The Core endpoint checks its internal bearer token and verifies synthetic
DB/event references. Even a successful match is NOT an independent evidence
capture, tenant authorization, or proof of runtime effect.

Configuration and credentials must be server-owned, never browser-supplied.
"""
import json
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from shared.acme_glpi_ticket_read import _qualified_projection
from shared.tenant_scope import reject_unqualified_tenant_scope

_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\Z")
_MAX_BYTES = 65536


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _origin(base_url):
    if not isinstance(base_url, str) or len(base_url) > 256:
        return None
    try:
        parsed = urlsplit(base_url)
        if (not parsed.hostname or parsed.username or parsed.password
                or parsed.query or parsed.fragment or parsed.path not in ("", "/")
                or parsed.scheme not in ("http", "https")
                or parsed.hostname != parsed.hostname.lower()):
            return None
        if parsed.scheme == "http":
            # Only the existing private Core service, never arbitrary HTTP.
            if parsed.hostname != "aiops2-core" or parsed.port != 810:
                return None
        elif parsed.port not in (None, 443, 810):
            return None
        return parsed.scheme + "://" + parsed.netloc.rstrip("/")
    except ValueError:
        return None


def _token(value):
    return (isinstance(value, str) and 16 <= len(value) <= 512
            and value.isascii() and not any(ch.isspace() for ch in value))


def _pairs_no_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _instant(value):
    if not isinstance(value, str) or not value or len(value) > 48:
        return None
    try:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            return None
        instant = parsed.astimezone(timezone.utc)
        if instant > datetime.now(timezone.utc) + timedelta(minutes=5):
            return None
        return instant
    except (ValueError, OverflowError):
        return None


def read_authenticated_core_evidence_refs(projection, *, base_url=None,
                                          bearer_token=None, opener=None):
    """Return a distinct status for authenticated synthetic Core references.

    This does not set verified_evidence_id(s): those denote independently
    authenticated evidence, not Core's synthetic reference inventory.
    """
    result = {"core_evidence_ref_ids_verified": [],
              "core_evidence_ref_verification": "UNKNOWN_NO_AUTHENTICATED_CORE_EVIDENCE_READ"}
    if not isinstance(projection, dict) or not _qualified_projection(projection):
        result["core_evidence_ref_verification"] = "UNKNOWN_INVALID_CORE_PROJECTION"
        return result
    run_id = projection.get("run_id")
    if not isinstance(run_id, str) or _ID.fullmatch(run_id) is None:
        result["core_evidence_ref_verification"] = "UNKNOWN_INVALID_CORE_PROJECTION"
        return result
    origin = _origin(base_url)
    if not origin or not _token(bearer_token):
        return result
    request = Request(origin + "/api/noc/runs/" + run_id + "/evidence-refs",
                      method="GET", headers={"Authorization": "Bearer " + bearer_token,
                                             "Accept": "application/json",
                                             "Cache-Control": "no-store"})
    try:
        client = opener if opener is not None else build_opener(ProxyHandler({}), _NoRedirect())
        with client.open(request, timeout=4) as response:
            if (response.status != 200 or not response.headers.get("Content-Type", "").lower().startswith("application/json")):
                return result
            raw = response.read(_MAX_BYTES + 1)
        if len(raw) > _MAX_BYTES:
            return result
        payload = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs_no_duplicates)
        if not isinstance(payload, dict):
            return result
        reject_unqualified_tenant_scope({k: v for k, v in payload.items()
                                         if k != "tenant_acl_qualified"})
        if (payload.get("schema") != "aiops.core-demo-evidence-refs.v1"
                or payload.get("run_id") != run_id
                or payload.get("classification") != "SYNTHETIC_ONLY"
                or payload.get("tenant_acl_qualified") is not False
                or payload.get("runtime_attested") is not False
                or payload.get("event_link_verified") is not True):
            return result
        items = payload.get("items")
        expected = projection["evidence_refs"]
        if not isinstance(items, list) or len(items) != len(expected):
            return result
        by_id = {x["evidence_id"]: x for x in expected}
        seen = set()
        for item in items:
            if not isinstance(item, dict) or set(item) != {"evidence_id", "source", "payload_sha256", "known_at"}:
                return result
            evidence_id = item.get("evidence_id")
            if (not isinstance(evidence_id, str) or evidence_id not in by_id
                    or evidence_id in seen):
                return result
            old = by_id[evidence_id]
            if (item.get("source") != old["source"]
                    or item.get("payload_sha256") != old["payload_sha256"]
                    or _instant(item.get("known_at")) is None
                    or _instant(item["known_at"]) != _instant(old["known_at"])):
                return result
            seen.add(evidence_id)
        if seen != set(by_id):
            return result
    except (OSError, ValueError, UnicodeError, TypeError, AttributeError, KeyError):
        return result
    result["core_evidence_ref_ids_verified"] = sorted(seen)
    result["core_evidence_ref_verification"] = "CORE_GET_200_SYNTHETIC_REFS_MATCH_NO_TENANT_ATTESTATION"
    return result
