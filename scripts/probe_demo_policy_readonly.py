#!/usr/bin/env python3
"""Fail-closed, read-only loopback probe of Core's persisted DEMO Policy gate.

Not a HITL/Temporal execution test, not tenant RBAC qualification and not a
deployment smoke-test. Never targets remote addresses or writes to Core.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{1,95}\Z")
_MAX_BYTES = 16 * 1024
_FLAGS = (
    "runtime_attested", "policy_http_verified", "hitl_approval_verified",
    "temporal_execution_verified", "postchecks_verified", "rollback_verified",
    "tenant_acl_qualified", "live_remediation_authorized",
)
_FIELDS = frozenset({
    "schema", "run_id", "incident_id", "mode", "run_status",
    "policy_gate_state", "policy_decision", "policy_gate_recorded",
    "explanation_code", "provenance", *_FLAGS,
})
_GATE_PAIRS = frozenset({
    ("MISSING", None, False),
    ("PASS", "SIMULATE", True),
    ("UNKNOWN", "HUMAN_APPROVAL", True),
    ("BLOCKED", "HUMAN_APPROVAL", True),
    ("BLOCKED", "ESCALATE", True),
})
_STATES = frozenset({
    "CREATED", "RUNNING", "WAITING", "BLOCKED", "RESOLVED", "FAILED", "CANCELLED",
})


class ProbeError(ValueError):
    """Fixed diagnostic only: never embed response body or token."""


def require(condition: bool, code: str) -> None:
    if not condition:
        raise ProbeError(code)


def loopback_url(base_url: str) -> str:
    try:
        url = urlsplit(base_url)
        port = url.port
    except ValueError:
        raise ProbeError("invalid_loopback_url") from None
    require(url.scheme == "http" and url.hostname == "127.0.0.1"
            and port is not None and 0 < port <= 65535
            and url.username is None and url.password is None
            and url.path in ("", "/") and not url.query and not url.fragment,
            "invalid_loopback_url")
    return "http://127.0.0.1:" + str(port)


def validate_observation(value: object, run_id: str, incident_id: str) -> dict:
    """Check Core's read-only response, never infer a remediation from a gate."""
    require(type(value) is dict and set(value) == _FIELDS, "invalid_contract_shape")
    require(value["schema"] == "aiops.core-demo-policy-observation.v1"
            and value["provenance"] == "CORE_POSTGRES_SYNTHETIC_READ",
            "invalid_provenance")
    require(value["run_id"] == run_id and value["incident_id"] == incident_id
            and value["mode"] == "DEMO" and isinstance(value["run_status"], str)
            and value["run_status"] in _STATES,
            "canonical_identity_mismatch")
    require(all(value[key] is False for key in _FLAGS), "unqualified_runtime_claim")
    require(isinstance(value["policy_gate_state"], str)
            and (value["policy_decision"] is None
                 or isinstance(value["policy_decision"], str))
            and type(value["policy_gate_recorded"]) is bool,
            "invalid_policy_disposition")
    pair = (value["policy_gate_state"], value["policy_decision"],
            value["policy_gate_recorded"])
    require(pair in _GATE_PAIRS, "invalid_policy_disposition")
    status = value["run_status"]
    if status == "BLOCKED":
        explanation = ("BLOCKED_WITHOUT_POLICY_GATE" if pair[0] == "MISSING"
                       else "BLOCKED_CAUSE_NOT_ESTABLISHED")
    elif status == "RESOLVED":
        explanation = ("RESOLVED_WITH_SIMULATE_GATE_NOT_LIVE"
                       if pair[:2] == ("PASS", "SIMULATE")
                       else "RESOLVED_POLICY_SIMULATION_UNVERIFIED")
    elif status == "RUNNING":
        explanation = "RUNNING_NO_TERMINAL_PROOF"
    else:
        explanation = "RUN_STATE_NOT_REMEDIATION_PROOF"
    require(value["explanation_code"] == explanation, "inconsistent_explanation")
    return {
        "schema": "aiops.demo-policy-readonly-probe.v1",
        "overall": "NO_GO",
        "observation_status": "CORE_READ_OBSERVED_NOT_E2E",
        "run_id": run_id,
        "incident_id": incident_id,
        "run_status": status,
        "policy_gate_state": pair[0],
        "policy_decision": pair[1],
        "explanation_code": explanation,
        "provenance": "CORE_HTTP_LOOPBACK_SYNTHETIC_READ",
        "runtime_attested": False,
        "tenant_acl_qualified": False,
        "live_remediation_authorized": False,
        "blockers": [
            "TEMPORAL_HITL_POSTCHECKS_EVIDENCE_NOT_TESTED",
            "TENANT_RBAC_AND_DEPLOYED_RUNTIME_NOT_ATTESTED",
        ],
    }


def compare_unbound_policy_values(
    core_observation: object, policy_response: object, run_id: str, incident_id: str,
) -> dict:
    """Compare two independent values, NEVER attest a Policy-to-Run binding.

    Policy /api/policy/check has no canonical run_id/incident_id or authenticated
    request binding. A matching decision is therefore not evidence that Policy
    produced the persisted Core gate. Only for synthetic read-model qualification.
    """
    validate_observation(core_observation, run_id, incident_id)
    require(type(policy_response) is dict
            and set(policy_response) == {"state", "decision", "reason"}
            and type(policy_response["state"]) is str
            and type(policy_response["decision"]) is str
            and type(policy_response["reason"]) is str
            and 0 < len(policy_response["reason"]) <= 512,
            "invalid_policy_http_contract")
    pair = (policy_response["state"], policy_response["decision"])
    require(pair in {
        ("PASS", "SIMULATE"), ("UNKNOWN", "HUMAN_APPROVAL"),
        ("BLOCKED", "HUMAN_APPROVAL"), ("BLOCKED", "ESCALATE"),
    }, "invalid_policy_http_disposition")
    require(core_observation["policy_gate_recorded"] is True
            and (core_observation["policy_gate_state"],
                 core_observation["policy_decision"]) == pair,
            "unbound_policy_core_mismatch")
    return {
        "schema": "aiops.demo-policy-unbound-value-crosscheck.v1",
        "overall": "NO_GO",
        "comparison": "VALUES_MATCH_NOT_CAUSAL_PROOF",
        "run_id": run_id,
        "incident_id": incident_id,
        "policy_gate_state": pair[0],
        "policy_decision": pair[1],
        "policy_input_provenance": "UNVERIFIED_CALLER_SUPPLIED_VALUE",
        "policy_run_binding_verified": False,
        "hitl_approval_verified": False,
        "temporal_execution_verified": False,
        "postchecks_verified": False,
        "live_remediation_authorized": False,
    }


def _unique_json_object(pairs: list[tuple[str, object]]) -> dict:
    """Reject duplicate keys at every nesting level, not only the top-level object."""
    value = {}
    for key, item in pairs:
        require(key not in value, "duplicate_core_json_key")
        value[key] = item
    return value


def _reject_nonfinite_json(_value: str) -> None:
    raise ProbeError("nonfinite_core_json")


def decode_core_json(raw: bytes) -> object:
    """Require canonical UTF-8 JSON; json.loads(bytes) also accepts UTF-16/32."""
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_json_object,
                          parse_constant=_reject_nonfinite_json)
    except ProbeError:
        raise
    except (ValueError, UnicodeError):
        raise ProbeError("invalid_core_json") from None


def validate_core_headers(headers) -> None:
    """Reject conflicting cache/media headers and compressed/recoded payloads."""
    cache = headers.get_all("Cache-Control", [])
    require(len(cache) == 1
            and "no-store" in {part.strip() for part in cache[0].lower().split(",")},
            "missing_no_store")
    media = headers.get_all("Content-Type", [])
    require(len(media) == 1 and headers.get_content_type() == "application/json"
            and headers.get_content_charset() in (None, "utf-8"),
            "invalid_content_type")
    encodings = headers.get_all("Content-Encoding", [])
    require(not encodings or (len(encodings) == 1
            and encodings[0].strip().lower() == "identity"),
            "invalid_content_encoding")


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


def probe(base_url: str, run_id: str, incident_id: str, token: str) -> dict:
    base = loopback_url(base_url)
    require(isinstance(run_id, str) and _ID.fullmatch(run_id) is not None
            and isinstance(incident_id, str) and _ID.fullmatch(incident_id) is not None,
            "invalid_canonical_id")
    require(isinstance(token, str) and 0 < len(token) <= 4096
            and token == token.strip()
            and all(33 <= ord(char) <= 126 for char in token),
            "missing_or_invalid_internal_token")
    request = Request(
        base + "/api/noc/runs/" + run_id + "/policy-status",
        headers={"Accept": "application/json", "Authorization": "Bearer " + token},
        method="GET",
    )
    opener = build_opener(ProxyHandler({}), NoRedirect)
    try:
        response = opener.open(request, timeout=4)
    except HTTPError:
        raise ProbeError("core_denied_or_unavailable") from None
    except (URLError, OSError, TimeoutError):
        raise ProbeError("core_unreachable") from None
    with response:
        require(response.status == 200, "core_denied_or_unavailable")
        validate_core_headers(response.headers)
        raw = response.read(_MAX_BYTES + 1)
    require(len(raw) <= _MAX_BYTES, "oversized_core_response")
    data = decode_core_json(raw)
    result = validate_observation(data, run_id, incident_id)
    result["observed_at_utc"] = datetime.now(timezone.utc).isoformat()
    result["clock_provenance"] = "PROBE_LOCAL_CLOCK_NOT_SERVER_ATTESTED"
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only Core DEMO Policy probe")
    parser.add_argument("--base-url", required=True,
                        help="Loopback Core HTTP only, e.g. http://127.0.0.1:1810")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--incident-id", required=True)
    args = parser.parse_args(argv)
    try:
        result = probe(args.base_url, args.run_id, args.incident_id,
                       os.environ.get("AIOPS_INTERNAL_TOKEN", ""))
    except ProbeError as exc:
        print(json.dumps({"schema": "aiops.demo-policy-readonly-probe.v1",
                          "overall": "NO_GO", "observation_status": "BLOCKED",
                          "reason": str(exc)}, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
