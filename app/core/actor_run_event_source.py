"""Negative-only, independent Core Incident/Run/source-event authority readback.

This adapter is a *necessary* actor-resource precondition, never ALLOW.
It performs an authenticated HTTPS read against a separately configured
read-only source authority, not a self-signed xref row or Portal assertion.
"""
from __future__ import annotations

import json
import os
import re
from urllib.parse import urlsplit

import requests

SCHEMA = "aiops.core-actor-run-event-binding.v1"
_HEX = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)
_EVENT = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{1,95}\Z", re.ASCII)
_FIELDS = ("tenant_id", "run_id", "incident_id", "glpi_instance_id",
           "ticket_id", "glpi_entity_id", "permission", "actor_subject",
           "source_event_id", "source_event_hash")


def _https_endpoint(url):
    if not isinstance(url, str) or not 16 <= len(url) <= 512:
        return False
    try:
        parsed = urlsplit(url)
        return (parsed.scheme == "https" and bool(parsed.hostname)
                and parsed.username is None and parsed.password is None
                and not parsed.query and not parsed.fragment
                and parsed.port in (None, 443, 8443)
                and parsed.path not in ("", "/") and parsed.geturl() == url)
    except ValueError:
        return False


def _source_run_event_preflight(claims, expected, record, now):
    """Return True only for exact, fresh, independently read source binding.

    No network is attempted without pinned tenant/instance configuration.
    No user-controlled URL or source hash is accepted. All errors fail closed.
    The response is never promoted to a positive actor authorization.
    """
    raw = os.getenv("AIOPS_XREF_ACTOR_CORE_SOURCE_JSON", "")
    if not isinstance(raw, str) or not raw or len(raw) > 16384:
        return False
    try:
        if not isinstance(claims, dict) or not isinstance(expected, dict) or not isinstance(record, dict):
            return False
        if type(now) is not int or not isinstance(claims.get("sub"), str) or not claims["sub"]:
            return False
        source_id = record.get("source_event_id")
        source_hash = record.get("source_payload_hash")
        if (not isinstance(source_id, str) or not _EVENT.fullmatch(source_id)
                or not isinstance(source_hash, str) or not _HEX.fullmatch(source_hash)):
            return False
        if any(record.get(k) != expected.get(k) for k in ("run_id", "incident_id", "glpi_entity_id")):
            return False
        cfgs = json.loads(raw)
        if not isinstance(cfgs, list) or not 1 <= len(cfgs) <= 16:
            return False
        matches = [c for c in cfgs if isinstance(c, dict)
                   and c.get("tenant_id") == expected.get("tenant_id")
                   and c.get("glpi_instance_id") == expected.get("glpi_instance_id")]
        if len(matches) != 1:
            return False
        cfg = matches[0]
        if set(cfg) != {"tenant_id", "glpi_instance_id", "url", "issuer",
                        "client_id", "client_secret"} or not _https_endpoint(cfg["url"]):
            return False
        if any(not isinstance(cfg[k], str) or not cfg[k].isascii()
               or not cfg[k].isprintable() or not 16 <= len(cfg[k]) <= 256
               for k in ("issuer", "client_id", "client_secret")):
            return False
        if len(cfg["client_secret"]) < 32:
            return False
        request = {k: expected[k] for k in _FIELDS if k in expected}
        request.update(actor_subject=claims["sub"], source_event_id=source_id,
                       source_event_hash=source_hash)
        if set(request) != set(_FIELDS) or any(not isinstance(v, str) or not v
                                               for v in request.values()):
            return False
        with requests.Session() as session:
            session.trust_env = False
            with session.post(
                cfg["url"], json=request,
                auth=(cfg["client_id"], cfg["client_secret"]),
                headers={"Accept": "application/json"}, timeout=(2, 3),
                allow_redirects=False, stream=True, verify=True
            ) as response:
                if (response.status_code != 200 or
                    response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
                        != "application/json"):
                    return False
                data = bytearray()
                for chunk in response.iter_content(chunk_size=4096):
                    data.extend(chunk)
                    if len(data) > 16384:
                        return False
                proof = json.loads(data.decode("utf-8"))
        if not isinstance(proof, dict) or set(proof) != set(_FIELDS) | {
                "schema", "issuer", "source_system", "observed_at",
                "known_at", "expires_at", "revoked", "verified"}:
            return False
        if (proof["schema"] != SCHEMA or proof["issuer"] != cfg["issuer"]
                or proof["source_system"] != "CORE_CANONICAL_READBACK"
                or proof["revoked"] is not False or proof["verified"] is not True):
            return False
        if any(type(proof.get(k)) is not str or proof[k] != value
               for k, value in request.items()):
            return False
        if (any(type(proof.get(k)) is not int
                for k in ("observed_at", "known_at", "expires_at"))
                or not now - 300 <= proof["observed_at"] <= proof["known_at"] <= now
                or not now < proof["expires_at"] <= now + 300
                or type(claims.get("exp")) is not int
                or proof["expires_at"] > claims["exp"]):
            return False
        return True
    except (OSError, ValueError, TypeError, KeyError, UnicodeError,
            requests.RequestException):
        return False
