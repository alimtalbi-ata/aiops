"""Versioned, negative-only seven-event Core source readback.

A separate HTTPS service with its own credentials and a read-only Core PG16
connection attests a complete seven-event snapshot. This is a necessary
source-integrity precondition, NOT native GLPI human authorization. No ALLOW,
VERIFIED, or ticket linkage decision is returned by this module.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from urllib.parse import urlsplit

import requests

SCHEMA = "aiops.core-canonical-seven-source-binding.v1"
PAYLOAD_DOMAIN = "aiops.core-source-event-payload.v1"
FULL_DOMAIN = "aiops.core-full-run-event.v1"
_HEX = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{1,95}\Z", re.ASCII)
_SCOPE = ("tenant_id", "incident_id", "run_id", "glpi_instance_id",
          "ticket_id", "glpi_entity_id", "permission", "actor_subject")
_FULL = ("event_id", "run_id", "incident_id", "tenant_id", "sequence",
         "stage", "event_type", "status", "evidence_id",
         "source_event_id", "source_payload_hash", "observed_at", "known_at")


def _digest(domain, value):
    raw = json.dumps({"schema": domain, "event": value}, sort_keys=True,
                     separators=(",", ":"), ensure_ascii=True).encode("ascii")
    return hashlib.sha256(raw).hexdigest()


def _endpoint(url):
    if not isinstance(url, str) or not 16 <= len(url) <= 512:
        return False
    try:
        p = urlsplit(url)
        return (p.scheme == "https" and bool(p.hostname) and p.username is None
                and p.password is None and not p.query and not p.fragment
                and p.path not in ("", "/") and p.port in (None, 443, 8443)
                and p.geturl() == url)
    except ValueError:
        return False


def _validate(proof, request, record, issuer, now, actor_exp):
    """Validate every byte-domain binding; 'verified' alone has no authority."""
    if (not isinstance(proof, dict)
            or set(proof) != set(_SCOPE) | {
                "schema", "issuer", "source_system", "observed_at",
                "known_at", "expires_at", "revoked", "events"}
            or proof.get("schema") != SCHEMA or proof.get("issuer") != issuer
            or proof.get("source_system") != "CORE_CANONICAL_READBACK"
            or proof.get("revoked") is not False):
        return False
    if any(type(proof.get(k)) is not str or proof[k] != v
           for k, v in request.items()):
        return False
    if (any(type(proof.get(k)) is not int
            for k in ("observed_at", "known_at", "expires_at"))
            or not now - 300 <= proof["observed_at"] <= proof["known_at"] <= now
            or not now < proof["expires_at"] <= min(now + 300, actor_exp)):
        return False
    events = proof.get("events")
    if not isinstance(events, list) or len(events) != 7:
        return False
    seen_events, seen_evidence, matching = set(), set(), 0
    last_known = 0
    for position, item in enumerate(events, 1):
        if not isinstance(item, dict) or set(item) != {
                "sequence", "source_event_id", "evidence_id", "payload",
                "payload_hash", "full_event", "full_event_hash"}:
            return False
        seq, event_id, evidence_id = (item["sequence"], item["source_event_id"],
                                      item["evidence_id"])
        if (type(seq) is not int or seq != position
                or not isinstance(event_id, str) or not _ID.fullmatch(event_id)
                or not isinstance(evidence_id, str) or not _ID.fullmatch(evidence_id)
                or event_id in seen_events or evidence_id in seen_evidence):
            return False
        seen_events.add(event_id)
        seen_evidence.add(evidence_id)
        payload, full = item["payload"], item["full_event"]
        if (not isinstance(payload, dict) or not isinstance(full, dict)
                or set(full) != set(_FULL)
                or any(not isinstance(item.get(k), str) or not _HEX.fullmatch(item[k])
                       for k in ("payload_hash", "full_event_hash"))):
            return False
        if (item["payload_hash"] != _digest(PAYLOAD_DOMAIN, payload)
                or item["full_event_hash"] != _digest(FULL_DOMAIN, full)
                or item["payload_hash"] == item["full_event_hash"]):
            return False
        if (full["sequence"] != seq or type(full["sequence"]) is not int
                or full["source_event_id"] != event_id
                or full["evidence_id"] != evidence_id
                or full["source_payload_hash"] != item["payload_hash"]
                or full["tenant_id"] != request["tenant_id"]
                or full["run_id"] != request["run_id"]
                or full["incident_id"] != request["incident_id"]
                or full["stage"] != "SOURCE" or full["event_type"] != "OBSERVED"
                or full["status"] != "PASS"
                or any(payload.get(k) != request[k]
                       for k in ("tenant_id", "run_id", "incident_id",
                                 "ticket_id", "glpi_entity_id"))
                or payload.get("source_event_id") != event_id
                or payload.get("sequence") != seq):
            return False
        observed, known = full["observed_at"], full["known_at"]
        if (type(observed) is not int or type(known) is not int
                or not now - 300 <= observed <= known <= now
                or known < last_known):
            return False
        last_known = known
        if event_id == record.get("source_event_id"):
            if item["payload_hash"] != record.get("source_payload_hash"):
                return False
            matching += 1
    return matching == 1


def canonical_seven_preflight(claims, expected, record, now):
    """Return source preflight bool only; NEVER a positive actor decision.

    Source HTTPS/TLS + Basic service authentication is independently configured.
    The response must bind seven *full* run-event hashes AND seven distinct
    payload hashes, without claiming equivalence to ACME full-event hashes.
    """
    raw = os.getenv("AIOPS_XREF_ACTOR_CANONICAL_SEVEN_JSON", "")
    if not isinstance(raw, str) or not raw or len(raw) > 16384:
        return False
    try:
        if (not isinstance(claims, dict) or not isinstance(expected, dict)
                or not isinstance(record, dict) or type(now) is not int
                or type(claims.get("exp")) is not int or claims["exp"] <= now
                or not isinstance(claims.get("sub"), str) or not claims["sub"]
                or not isinstance(record.get("source_event_id"), str)
                or not _ID.fullmatch(record["source_event_id"])
                or not isinstance(record.get("source_payload_hash"), str)
                or not _HEX.fullmatch(record["source_payload_hash"])):
            return False
        if any(record.get(k) != expected.get(k)
               for k in ("run_id", "incident_id", "glpi_entity_id")):
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
        if (set(cfg) != {"tenant_id", "glpi_instance_id", "url", "issuer",
                         "client_id", "client_secret"}
                or not _endpoint(cfg["url"])
                or any(not isinstance(cfg[k], str) or not cfg[k].isascii()
                       or not cfg[k].isprintable() or not 16 <= len(cfg[k]) <= 256
                       for k in ("issuer", "client_id", "client_secret"))
                or len(cfg["client_secret"]) < 32):
            return False
        request = {k: expected[k] for k in _SCOPE if k in expected}
        request["actor_subject"] = claims["sub"]
        if (set(request) != set(_SCOPE)
                or any(not isinstance(v, str) or not v for v in request.values())
                or request["permission"] != "run:read"):
            return False
        with requests.Session() as session:
            session.trust_env = False
            with session.post(
                cfg["url"], json=request,
                auth=(cfg["client_id"], cfg["client_secret"]),
                headers={"Accept": "application/json"},
                timeout=(2, 3), allow_redirects=False,
                stream=True, verify=True
            ) as response:
                if (response.status_code != 200 or
                        response.headers.get("Content-Type", "").split(";", 1)[0]
                        .strip().lower() != "application/json"):
                    return False
                body = bytearray()
                for chunk in response.iter_content(chunk_size=4096):
                    body.extend(chunk)
                    if len(body) > 65536:
                        return False
                proof = json.loads(body.decode("utf-8"))
        return _validate(proof, request, record, cfg["issuer"], now, claims["exp"])
    except (OSError, ValueError, TypeError, KeyError, UnicodeError,
            OverflowError, requests.RequestException):
        return False
