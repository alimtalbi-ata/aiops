"""Fail-closed Core preflight for independently authenticated GLPI human rights.

This is a *source contract*, not an authorization decision. A synthetic mapping
HMAC, a 200 from a mocked GLPI server, and OIDC introspection do not grant
ALLOW. Core's actor-resource-authorization.v1 remains UNKNOWN until a real,
independently qualified issuer/GLPI trust path and durable replay fence exist.
No GLPI write operation is implemented.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
from urllib.parse import urlsplit

import requests

_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{1,95}\Z", re.ASCII)
_HEX = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)
_NUM = re.compile(r"[0-9]{1,18}\Z", re.ASCII)


def _origin(value, *, path=False):
    if not isinstance(value, str) or len(value) > 512:
        return False
    try:
        p = urlsplit(value)
        return (p.scheme == "https" and bool(p.hostname) and not p.username
                and not p.password and not p.query and not p.fragment
                and p.port in (None, 443, 8443)
                and (p.path not in ("", "/") if path else p.path in ("", "/"))
                and p.geturl() == value)
    except ValueError:
        return False


def _read_json(session, method, url, headers, *, auth=None, payload=None):
    kwargs = dict(headers=headers, timeout=(2, 3), allow_redirects=False,
                  stream=True, verify=True)
    if auth is not None:
        kwargs["auth"] = auth
    if payload is not None:
        kwargs["json"] = payload
    with (session.post(url, **kwargs) if method == "POST"
          else session.get(url, **kwargs)) as response:
        if (response.status_code != 200 or
                response.headers.get("Content-Type", "").split(";", 1)[0]
                .strip().lower() != "application/json"):
            raise ValueError("source refused or unexpected content type")
        data = bytearray()
        for chunk in response.iter_content(chunk_size=4096):
            data.extend(chunk)
            if len(data) > 65536:
                raise ValueError("source response too large")
        return json.loads(data.decode("utf-8"))


def _mapping_mac(mapping, key):
    fields = {k: v for k, v in mapping.items() if k != "binding_mac"}
    raw = json.dumps({"schema": "aiops.core-oidc-glpi-actor-binding.v1",
                      "binding": fields}, sort_keys=True,
                     separators=(",", ":"), ensure_ascii=True).encode("ascii")
    return hmac.new(key.encode("ascii"), raw, hashlib.sha256).hexdigest()


def _native_glpi_preflight(claims, expected, now):
    """Check issuer-authenticated subject mapping AND native actor GLPI reads.

    Returns only a preflight boolean. It is never an ALLOW or VERIFIED signal.
    The mapping service and GLPI must be distinct HTTPS origins with separately
    held credentials; the GLPI session must be a *human actor* session, not the
    service readback session used by the xref endpoint.
    """
    raw = os.getenv("AIOPS_XREF_ACTOR_NATIVE_SOURCES_JSON", "")
    if not raw or len(raw) > 16384 or not isinstance(claims, dict):
        return False
    try:
        configs = json.loads(raw)
        if not isinstance(configs, list) or not 1 <= len(configs) <= 16:
            return False
        matches = [c for c in configs if isinstance(c, dict)
                   and c.get("tenant_id") == expected.get("tenant_id")
                   and c.get("glpi_instance_id") == expected.get("glpi_instance_id")]
        if len(matches) != 1:
            return False
        cfg = matches[0]
        if set(cfg) != {"tenant_id", "glpi_instance_id", "mapping_url",
                        "mapping_client_id", "mapping_client_secret",
                        "mapping_mac_key", "glpi_origin", "glpi_app_token"}:
            return False
        if not _origin(cfg["mapping_url"], path=True) or not _origin(cfg["glpi_origin"]):
            return False
        if urlsplit(cfg["mapping_url"]).netloc == urlsplit(cfg["glpi_origin"]).netloc:
            return False
        if any(not isinstance(cfg[k], str) or not cfg[k].isascii()
               or not cfg[k].isprintable() or not 16 <= len(cfg[k]) <= 512
               for k in ("mapping_client_id", "mapping_client_secret", "glpi_app_token")):
            return False
        if (not isinstance(cfg["mapping_mac_key"], str)
                or not cfg["mapping_mac_key"].isascii()
                or not cfg["mapping_mac_key"].isprintable()
                or not 32 <= len(cfg["mapping_mac_key"]) <= 512):
            return False
        if (not isinstance(claims.get("sub"), str) or not isinstance(claims.get("iss"), str)
                or not isinstance(claims.get("jti"), str)
                or type(claims.get("glpi_user_id")) is not int
                or claims["glpi_user_id"] < 1
                or type(claims.get("exp")) is not int
                or not now < claims["exp"] <= now + 300):
            return False
        for key in ("tenant_id", "glpi_instance_id", "ticket_id", "glpi_entity_id"):
            if not isinstance(expected.get(key), str):
                return False
        if not _NUM.fullmatch(expected["ticket_id"]) or not _NUM.fullmatch(expected["glpi_entity_id"]):
            return False
        request = {"subject": claims["sub"], "issuer": claims["iss"],
                   "tenant_id": expected["tenant_id"],
                   "glpi_instance_id": expected["glpi_instance_id"],
                   "glpi_user_id": claims["glpi_user_id"],
                   "jti": claims["jti"], "nonce": expected["nonce"]}
        with requests.Session() as session:
            session.trust_env = False
            mapping = _read_json(session, "POST", cfg["mapping_url"],
                                 {"Accept": "application/json"},
                                 auth=(cfg["mapping_client_id"], cfg["mapping_client_secret"]),
                                 payload=request)
            if not isinstance(mapping, dict) or set(mapping) != set(request) | {
                    "source_event_id", "issued_at", "expires_at", "revoked",
                    "glpi_session_token", "binding_mac", "schema_version"}:
                return False
            if any(mapping.get(k) != v or type(mapping.get(k)) is not type(v)
                   for k, v in request.items()):
                return False
            if (mapping["schema_version"] != "aiops.core-oidc-glpi-actor-binding.v1"
                    or mapping["revoked"] is not False
                    or type(mapping["issued_at"]) is not int
                    or type(mapping["expires_at"]) is not int
                    or not now - 300 <= mapping["issued_at"] <= now < mapping["expires_at"]
                    or mapping["expires_at"] > claims["exp"]
                    or not isinstance(mapping["source_event_id"], str)
                    or not _ID.fullmatch(mapping["source_event_id"])
                    or not isinstance(mapping["glpi_session_token"], str)
                    or not 16 <= len(mapping["glpi_session_token"]) <= 512
                    or not mapping["glpi_session_token"].isascii()
                    or not mapping["glpi_session_token"].isprintable()
                    or not isinstance(mapping["binding_mac"], str)
                    or not _HEX.fullmatch(mapping["binding_mac"])
                    or not hmac.compare_digest(mapping["binding_mac"],
                                               _mapping_mac(mapping, cfg["mapping_mac_key"]))):
                return False
            headers = {"Accept": "application/json", "App-Token": cfg["glpi_app_token"],
                       "Session-Token": mapping["glpi_session_token"]}
            base = cfg["glpi_origin"].rstrip("/") + "/apirest.php"
            session_data = _read_json(session, "GET", base + "/getFullSession", headers)
            native = session_data.get("session") if isinstance(session_data, dict) else None
            if not isinstance(native, dict) or type(native.get("glpiID")) is not int:
                return False
            if native["glpiID"] != claims["glpi_user_id"]:
                return False
            profile = native.get("glpiactiveprofile")
            entities = native.get("glpiactiveentities")
            if (not isinstance(profile, dict) or type(profile.get("id")) is not int
                    or profile["id"] < 1 or not isinstance(entities, list)
                    or not 1 <= len(entities) <= 128
                    or any(type(i) is not int or i < 0 for i in entities)
                    or int(expected["glpi_entity_id"]) not in entities):
                return False
            for path, key, number in (
                    ("User", "id", claims["glpi_user_id"]),
                    ("Profile", "id", profile["id"]),
                    ("Entity", "id", int(expected["glpi_entity_id"])),
                    ("Ticket", "id", int(expected["ticket_id"]))):
                obj = _read_json(session, "GET", base + "/" + path + "/" + str(number), headers)
                if not isinstance(obj, dict) or type(obj.get(key)) is not int or obj[key] != number:
                    return False
                # A profile identifier is not a permission. Require GLPI's
                # native READ bit (1) on the ticket right, plus a successful
                # human-session GET of this exact Ticket and Entity. READMY
                # or a synthetic mapping/HMAC alone cannot satisfy this gate.
                if path == "Profile":
                    rights = obj.get("ticket")
                    if type(rights) is not int or (rights & 1) != 1:
                        return False
                if path == "User" and (type(obj.get("is_active")) is not int
                                       or obj["is_active"] != 1):
                    return False
                if path == "Ticket" and (type(obj.get("entities_id")) is not int
                                         or obj["entities_id"] != int(expected["glpi_entity_id"])):
                    return False
        return True
    except (OSError, ValueError, TypeError, KeyError, UnicodeError,
            OverflowError, requests.RequestException):
        return False
