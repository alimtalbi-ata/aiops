"""Offline, provider-neutral ACME viewer identity integration preflight.

This checks *configuration shape only*. It never fetches discovery/JWKS, verifies
JWTs, authenticates actors, or grants tenant/run access. No network or secrets.
"""
from __future__ import annotations

from urllib.parse import urlsplit
import ipaddress
import re

REQUIRED = ("issuer", "client_id", "audience", "tenant_acl_source", "run_acl_source")


def assess_oidc_integration(config: object) -> dict:
    result = {"schema": "aiops.acme-oidc-integration-preflight.v1",
              "status": "NO_GO", "reason": "OIDC_AUTHORITY_NOT_RUNTIME_VERIFIED",
              "identity_runtime_verified": False, "tenant_acl_runtime_verified": False,
              "exact_run_acl_runtime_verified": False, "browser_evidence_enabled": False}
    if not isinstance(config, dict) or set(config) != set(REQUIRED):
        return {**result, "reason": "OIDC_CONFIGURATION_INCOMPLETE"}
    if any(type(config[k]) is not str or not config[k] or len(config[k]) > 256
           or config[k] != config[k].strip() for k in REQUIRED):
        return {**result, "reason": "OIDC_CONFIGURATION_INVALID"}
    issuer = config["issuer"]
    try:
        parsed = urlsplit(issuer)
        hostname = parsed.hostname or ""
        try:
            ipaddress.ip_address(hostname)
            is_ip_literal = True
        except ValueError:
            is_ip_literal = False
        valid = (parsed.scheme == "https" and bool(hostname)
                 and not is_ip_literal
                 and re.fullmatch(r"[A-Za-z0-9.-]+", hostname) is not None
                 and "." in hostname and ".." not in hostname
                 and not any(ch.isspace() or ord(ch) < 33 for ch in issuer)
                 and chr(92) not in issuer
                 and not parsed.username and not parsed.password
                 and not parsed.query and not parsed.fragment
                 and parsed.port in (None, 443)
                 and parsed.hostname not in ("localhost", "127.0.0.1", "::1")
                 and not parsed.hostname.endswith(".localhost"))
    except ValueError:
        valid = False
    if not valid:
        return {**result, "reason": "OIDC_ISSUER_NOT_QUALIFIED"}
    if config["tenant_acl_source"] == config["run_acl_source"] == "client_claims":
        return {**result, "reason": "ACL_AUTHORITY_NOT_QUALIFIED"}
    if "client_claims" in (config["tenant_acl_source"], config["run_acl_source"]):
        return {**result, "reason": "ACL_AUTHORITY_NOT_QUALIFIED"}
    # Even structurally valid values are caller-supplied, not authoritative.
    # Never return 200, GO, or a viewer authorization decision.
    return result
