#!/usr/bin/env python3
"""Read-only ACME portal contract qualification against an ephemeral loopback server.

This is NOT an end-to-end Core/Temporal/GLPI/Evidence qualification. The only
POST is the existing stateless Explore/Story cursor projection; no /api/demo
command, runtime mutation, screenshot or external address is ever requested.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

MAX_RESPONSE_BYTES = 512 * 1024
CUES = ("detect", "correlate", "enrich", "analyze", "ticket",
        "approve", "simulate", "verify", "close")
PATH = ("SAN-FABRIC-A", "HOST-ESX-01", "VM-PAY-01", "APP-PAY-01")
BLOCKERS = (
    "CORE_TEMPORAL_ANALYST_CRITIC_POLICY_EVIDENCE_NOT_TESTED",
    "GLPI_N8N_GRAFANA_NOT_TESTED",
    "TENANT_RBAC_RUNTIME_NOT_TESTED",
    "INDEPENDENT_EVIDENCE_AND_OPERATOR_CAPTURE_MISSING",
    "CUSTOMER_VIDEO_NOT_QUALIFIED",
)


class QualificationError(ValueError):
    """Fixed diagnostic code only; never include credentials or response data."""


def require(ok: bool, code: str) -> None:
    if not ok:
        raise QualificationError(code)


def validate_pair(impact: object, story: object) -> dict:
    """Compare actual portal JSON documents; fail closed on false attestations."""
    require(type(impact) is dict and type(story) is dict, "invalid_json_shape")
    require(impact.get("schema") == "aiops.synthetic-impact-read-model.v1",
            "impact_schema_mismatch")
    require(story.get("schema") == "aiops.acme-explore-story.v1",
            "story_schema_mismatch")
    require(impact.get("provenance") == story.get("provenance") == "SIMULATED_TARGET",
            "provenance_mismatch")
    digest = impact.get("source_sha256")
    require(type(digest) is str and re.fullmatch(r"[a-f0-9]{64}", digest) is not None
            and story.get("source_sha256") == digest, "fixture_digest_mismatch")
    run_id = "SIM-ACME-" + digest[:16].upper()
    require(impact.get("run_id") == run_id and
            impact.get("run_id_provenance") == "DERIVED_FROM_FIXTURE_SHA256_NOT_RUNTIME_RUN",
            "synthetic_run_id_mismatch")
    require(impact.get("incident_id") == "ACME-DEMO-SAN-001" and
            impact.get("impact_incident_id") == "ACME-DEMO-PAY-002",
            "canonical_incident_mismatch")
    require(impact.get("impact_path") == list(PATH), "impact_path_mismatch")
    require(impact.get("ticket_id") is None and
            impact.get("event_timestamp_utc") is None and
            impact.get("runtime_evidence_present") is False,
            "impact_runtime_claim")
    require(impact.get("ticket_id_provenance") == "ABSENT_NO_GLPI_WRITE",
            "ticket_provenance_mismatch")
    for key in ("runtime_attested", "production_qualified", "live_remediation_authorized"):
        require(impact.get(key) is False and story.get(key) is False,
                "false_runtime_attestation")
    decision = impact.get("decision_preview")
    require(type(decision) is dict and type(decision.get("policy")) is dict
            and decision["policy"].get("decision") == "DENY_LIVE_ACTION"
            and decision.get("live_execution") is False
            and decision.get("backend_writes") is False,
            "policy_preview_not_fail_closed")
    scenario = story.get("scenario")
    require(type(scenario) is dict, "scenario_missing")
    for key in ("run_id", "incident_id", "impact_incident_id", "impact_path"):
        require(scenario.get(key) == impact.get(key), "scenario_" + key + "_mismatch")
    require(scenario.get("ticket_id") is None and
            scenario.get("event_timestamp_utc") is None,
            "scenario_runtime_claim")
    require(story.get("action") == "start" and story.get("mode") == "explore"
            and story.get("cursor") == 0 and story.get("playing") is False,
            "story_cursor_mismatch")
    checkpoints, timeline = impact.get("checkpoint_evidence"), story.get("timeline")
    require(type(checkpoints) is list and type(timeline) is list
            and len(checkpoints) == len(timeline) == len(CUES),
            "checkpoint_count_mismatch")
    for index, (checkpoint, event) in enumerate(zip(checkpoints, timeline)):
        require(type(checkpoint) is dict and type(event) is dict
                and checkpoint.get("cue") == event.get("cue") == CUES[index]
                and checkpoint.get("service") == event.get("service")
                and checkpoint.get("view") == event.get("view"),
                "checkpoint_identity_mismatch")
        require(checkpoint.get("status") == event.get("status") == "MISSING"
                and checkpoint.get("screenshot_sha256") is None
                and checkpoint.get("event_timestamp_utc") is None
                and checkpoint.get("runtime_authenticated") is False
                and checkpoint.get("source") == "CHECKPOINT_CONTRACT_ONLY_NO_CAPTURE",
                "checkpoint_falsely_attested")
    require(story.get("step") == timeline[0], "story_step_mismatch")
    return {
        "schema": "aiops.acme-readonly-qualification.v1",
        "scope": "EPHEMERAL_PORTAL_SIMULATED_CONTRACT_ONLY",
        "contract_status": "PASS",
        "overall": "NO_GO",
        "provenance": "SIMULATED_TARGET",
        "run_id": run_id,
        "incident_id": impact["incident_id"],
        "impact_incident_id": impact["impact_incident_id"],
        "source_sha256": digest,
        "checkpoint_count": len(CUES),
        "runtime_attested": False,
        "blockers": list(BLOCKERS),
    }


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


def loopback_base(url: str) -> str:
    parsed = urlsplit(url)
    require(parsed.scheme == "http" and parsed.hostname == "127.0.0.1"
            and parsed.port is not None and 0 < parsed.port <= 65535
            and not parsed.username and not parsed.password
            and parsed.path in ("", "/") and not parsed.query and not parsed.fragment,
            "non_loopback_or_invalid_url")
    return "http://127.0.0.1:" + str(parsed.port)


def request_json(base: str, path: str, payload: dict | None = None,
                 token: str | None = None) -> tuple[int, dict | None]:
    headers = {"Accept": "application/json"}
    data = None
    if payload is not None:
        data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token is not None:
        headers["Authorization"] = "Bearer " + token
    request = Request(base + path, data=data, headers=headers,
                      method="POST" if data is not None else "GET")
    opener = build_opener(NoRedirect)
    try:
        response = opener.open(request, timeout=4)
    except HTTPError as exc:
        if exc.code == 401:
            return 401, None
        raise QualificationError("unexpected_http_status") from None
    except (URLError, TimeoutError, OSError):
        raise QualificationError("portal_unreachable") from None
    with response:
        require(response.status == 200, "unexpected_http_status")
        require(response.headers.get("Cache-Control") == "no-store",
                "missing_no_store")
        require(response.headers.get_content_type() == "application/json",
                "invalid_content_type")
        raw = response.read(MAX_RESPONSE_BYTES + 1)
    require(len(raw) <= MAX_RESPONSE_BYTES, "oversized_response")
    try:
        value = json.loads(raw)
    except (UnicodeError, ValueError):
        raise QualificationError("invalid_json") from None
    require(type(value) is dict, "invalid_json_shape")
    return 200, value


def qualify(base_url: str, token: str) -> dict:
    base = loopback_base(base_url)
    require(bool(token.strip()), "missing_viewer_token")
    payload = {"action": "start", "cursor": 0, "mode": "explore"}
    anonymous_status, _ = request_json(base, "/api/demo/explore-story/control", payload)
    require(anonymous_status == 401, "anonymous_access_not_denied")
    _, impact = request_json(base, "/api/demo/acme-impact")
    _, story = request_json(base, "/api/demo/explore-story/control", payload, token)
    return validate_pair(impact, story)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ACME read-only loopback qualification")
    parser.add_argument("--base-url", required=True,
                        help="Ephemeral loopback portal, e.g. http://127.0.0.1:7777")
    args = parser.parse_args(argv)
    try:
        result = qualify(args.base_url, os.environ.get("AIOPS_PORTAL_READ_TOKEN", ""))
    except (QualificationError, ValueError) as exc:
        result = {"schema": "aiops.acme-readonly-qualification.v1",
                  "scope": "EPHEMERAL_PORTAL_SIMULATED_CONTRACT_ONLY",
                  "contract_status": "BLOCKED", "overall": "NO_GO",
                  "reason": str(exc), "blockers": list(BLOCKERS)}
        print(json.dumps(result, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
