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
# Canonical checkpoint targets reused from the ACME scenario contract (PR #133).
# These are storyboard expectations, NOT observed application states.
TARGETS = (
    ("detect", "prometheus", "source_alert", "firing", "monitoring_event_management", "noc_l1", "monitoring_to_noc_l1", "source_event_id_observed_at_dedupe_key"),
    ("correlate", "twin", "service_dependency_path", "source_backed", "service_configuration_management", "noc_l2", "noc_l1_to_noc_l2", "ci_service_edge_source_and_freshness"),
    ("acknowledge", "service_desk", "incident_intake", "acknowledged", "incident_management", "service_desk_n1", "noc_l1_to_service_desk_n1", "actor_timestamp_assignment_and_sla_start"),
    ("assess_impact", "core", "impact_urgency_priority", "assessed", "incident_management", "incident_manager_n2", "n1_to_incident_manager_n2", "impact_urgency_policy_version_and_rationale"),
    ("declare_major", "major_incident", "command_and_communications", "declared", "incident_management", "incident_commander", "n2_to_incident_commander", "commander_assignment_and_customer_update"),
    ("collect_evidence", "evidence", "evidence_bundle", "collected", "monitoring_event_management", "sre_n3", "incident_commander_to_sre_n3", "evidence_id_hash_source_observed_at_known_at"),
    ("retrieve_knowledge", "rag", "runbook_and_known_error", "retrieved", "knowledge_management", "knowledge_manager", "sre_n3_to_knowledge_manager", "document_version_acl_owner_and_citations"),
    ("analyze_root_cause", "analyst_critic", "hypothesis_and_challenge", "reviewed", "problem_management", "problem_manager_n3", "knowledge_manager_to_problem_manager_n3", "hypothesis_evidence_contradictions_and_critic_disposition"),
    ("propose_change", "policy", "risk_and_rollback_plan", "proposed", "change_enablement", "change_manager", "problem_manager_to_change_manager", "risk_scope_preconditions_postconditions_and_rollback"),
    ("approve_change", "hitl", "human_decision", "approved_simulation_only", "change_enablement", "authorized_approver", "change_manager_to_authorized_approver", "verified_identity_role_scope_nonce_expiry_and_proposal_hash"),
    ("simulate_action", "temporal", "sandbox_simulation", "simulated_no_effect", "deployment_management", "automation_operator", "approver_to_automation_operator", "simulation_receipt_execution_allowed_false"),
    ("verify_recovery", "verification", "service_health_and_slo", "verified", "service_validation_testing", "independent_verifier", "automation_operator_to_independent_verifier", "independent_postcondition_evidence_and_before_after"),
    ("close_incident", "service_desk", "incident_closure", "resolved", "incident_management", "service_desk_n1", "independent_verifier_to_service_desk_n1", "resolution_code_customer_confirmation_and_timeline"),
    ("problem_review", "continual_improvement", "pir_known_error_and_actions", "reviewed", "continual_improvement", "service_owner", "service_desk_to_service_owner", "verified_cause_action_owner_due_date_and_knowledge_review"),
)
CUES = tuple(target[0] for target in TARGETS)
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
    require(impact.get("simulation_ticket_id") == "SIM-GLPI-" + digest[:12].upper()
            and impact.get("simulation_ticket_provenance") ==
            "SYNTHETIC_LABEL_NOT_A_GLPI_TICKET",
            "synthetic_ticket_binding_mismatch")
    require(impact.get("evidence_source") == "LOCAL_SYNTHETIC_FIXTURE"
            and impact.get("timestamp_provenance") == "ABSENT_NO_RUNTIME_EVENT"
            and impact.get("simulation_timestamp_provenance") ==
            "FIXED_SCENARIO_CLOCK_NOT_RUNTIME_EVENT",
            "synthetic_source_provenance_mismatch")
    for key in ("runtime_attested", "production_qualified", "live_remediation_authorized"):
        require(impact.get(key) is False and story.get(key) is False,
                "false_runtime_attestation")
    decision = impact.get("decision_preview")
    require(type(decision) is dict and type(decision.get("policy")) is dict
            and type(decision.get("analyst")) is dict
            and type(decision.get("critic")) is dict
            and decision.get("provider") == "DETERMINISTIC_RULES_NOT_LLM"
            and decision["analyst"].get("status") == "HYPOTHESIS_ONLY"
            and decision["critic"].get("decision") == "HOLD_FOR_HUMAN_REVIEW"
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
        (cue, service, view, expected_state, practice, owner_role,
         handoff, evidence_required) = TARGETS[index]
        require(type(checkpoint) is dict and type(event) is dict
                and checkpoint.get("cue") == event.get("cue") == cue
                and checkpoint.get("service") == event.get("service") == service
                and checkpoint.get("view") == event.get("view") == view
                and checkpoint.get("required_state") == expected_state
                and checkpoint.get("itil_practice") == event.get("itil_practice") == practice
                and checkpoint.get("owner_role") == event.get("owner_role") == owner_role
                and checkpoint.get("handoff") == event.get("handoff") == handoff
                and checkpoint.get("evidence_required") == event.get("evidence_required") == evidence_required,
                "checkpoint_target_mismatch")
        require(checkpoint.get("status") == event.get("status") == "MISSING"
                and checkpoint.get("screenshot_sha256") is None
                and checkpoint.get("event_timestamp_utc") is None
                and checkpoint.get("runtime_authenticated") is False
                and checkpoint.get("source") == "SYNTHETIC_ITIL_CHECKPOINT_CONTRACT_ONLY_NO_CAPTURE",
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
        "checkpoint_count": len(TARGETS),
        "runtime_attested": False,
        "blockers": list(BLOCKERS),
    }


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


def loopback_base(url: str) -> str:
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError:
        raise QualificationError("non_loopback_or_invalid_url") from None
    require(parsed.scheme == "http" and parsed.hostname == "127.0.0.1"
            and port is not None and 0 < port <= 65535
            and not parsed.username and not parsed.password
            and parsed.path in ("", "/") and not parsed.query and not parsed.fragment,
            "non_loopback_or_invalid_url")
    return "http://127.0.0.1:" + str(port)


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
    require(token == token.strip() and len(token) <= 4096
            and all(32 <= ord(char) <= 126 for char in token),
            "invalid_viewer_token")
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
    except QualificationError as exc:
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
