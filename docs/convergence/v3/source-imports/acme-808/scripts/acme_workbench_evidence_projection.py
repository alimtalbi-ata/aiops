"""Fail-closed, presentation-only ACME Workbench evidence projection.

No I/O, identity, authorization, browser routes or runtime effects.
Untrusted receipts must never promote offline or local fake HTTP tests to GO.
"""
from __future__ import annotations

from scripts.acme_autonomous_loop_qualification import STAGES

SCENES = ("noc", "signals", "twin", "analyst_critic", "policy_hitl",
          "itsm_worker", "timeline")


def project_workbench_evidence(loop: object, readback: object,
                               routes: object) -> dict:
    result = {
        "schema": "aiops.acme-workbench-evidence-projection.v1",
        "status": "NO_GO",
        "scope": "ACME-TEST/SIMULATION",
        "source_trust": "UNTRUSTED_SUPPLIED_DATA",
        "autonomous_execution_allowed": False,
        "live": "NO_GO",
        "stages": {stage: "NOT_VERIFIED" for stage in STAGES},
        "scenes": {scene: "NOT_VERIFIED" for scene in SCENES},
        "readback": "NOT_VERIFIED",
        "viewer_acl": "NOT_VERIFIED",
        "browser_e2e": "NOT_VERIFIED",
        "deployed_sha": "NOT_VERIFIED",
        "remediation_effect": "NOT_VERIFIED",
        "learning": "NOT_VERIFIED",
    }
    if not all(type(x) is dict for x in (loop, readback, routes)):
        return {**result, "reason": "EVIDENCE_MISSING_OR_INVALID"}
    if (loop.get("schema") != "aiops.acme-autonomous-loop-qualification.v1"
            or readback.get("schema") != "aiops.acme-readonly-runtime-recipe.v1"
            or routes.get("schema") != "aiops.acme-portal-route-inventory.v1"):
        return {**result, "reason": "EVIDENCE_SCHEMA_MISMATCH"}
    if (loop.get("real_execution_allowed") is not False
            or loop.get("runtime_attested") is not False
            or loop.get("learning_claim_verified") is not False
            or readback.get("real_execution_allowed") is not False
            or readback.get("viewer_acl_verified") is not False
            or readback.get("browser_verified") is not False
            or readback.get("remediation_effect_verified") is not False
            or readback.get("autonomous_closed_loop_verified") is not False
            or readback.get("deployed_sha_attested") is not False
            or readback.get("learning_claim_verified") is not False
            or routes.get("seven_scenes_browser_qualified") is not False
            or routes.get("live") != "NO_GO"):
        return {**result, "reason": "UNSAFE_OR_UNSUPPORTED_ATTESTATION"}
    stages = loop.get("stages")
    scene_records = routes.get("scenes")
    if (type(stages) is not dict or set(stages) != set(STAGES)
            or type(scene_records) is not list or len(scene_records) != len(SCENES)):
        return {**result, "reason": "COVERAGE_INVALID"}
    allowed = {"NOT_VERIFIED", "OFFLINE_DECLARED_ONLY"}
    if any(type(v) is not str or v not in allowed for v in stages.values()):
        return {**result, "reason": "STAGE_ATTESTATION_UNSUPPORTED"}
    if (stages["REMEDIATION_EFFECT"] != "NOT_VERIFIED"
            or stages["LEARN"] != "NOT_VERIFIED"):
        return {**result, "reason": "EFFECT_OR_LEARNING_NOT_PROVEN"}
    scenes = {}
    for item in scene_records:
        if (type(item) is not dict or item.get("scene") not in SCENES
                or item["scene"] in scenes or item.get("browser_execution") != "NOT_TESTED"
                or item.get("deployed_route") != "NOT_VERIFIED"
                or item.get("selector") != "NOT_VERIFIED"
                or item.get("status") not in ("SOURCE_ROUTE_CANDIDATE_ONLY",
                                               "NOT_IMPLEMENTED")):
            return {**result, "reason": "SCENE_ATTESTATION_UNSUPPORTED"}
        scenes[item["scene"]] = item["status"]
    if set(scenes) != set(SCENES):
        return {**result, "reason": "SCENE_COVERAGE_INVALID"}
    if loop.get("status") not in ("OFFLINE_CONSISTENT_ONLY", "NO_GO"):
        return {**result, "reason": "LOOP_STATUS_UNSUPPORTED"}
    if readback.get("status") not in ("RUNTIME_READBACK_CONSISTENT_ONLY", "NO_GO"):
        return {**result, "reason": "READBACK_STATUS_UNSUPPORTED"}
    return {**result, "status": "EVIDENCE_PROJECTION_ONLY",
            "reason": "NO_TRUSTED_RUNTIME_OR_VIEWER_ATTESTATION",
            "stages": dict(stages), "scenes": scenes,
            "readback": ("SUPPLIED_READBACK_CONSISTENT_ONLY"
                         if readback["status"] == "RUNTIME_READBACK_CONSISTENT_ONLY"
                         else "NOT_VERIFIED")}
