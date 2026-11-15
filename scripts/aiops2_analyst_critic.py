"""Deterministic evidence-bound Analyst/Critic for isolated AIOps demonstrations.

This module does not call an LLM, execute remediation, or attest live runtime.
"""
from __future__ import annotations

import re

from aiops2_event_correlation import InvalidEvent

DIGEST = re.compile(r"^[0-9a-f]{64}$")


def analyze_and_critique(incident: object, impact: object) -> dict:
    """Produce a synthetic hypothesis using upstream evidence references.

    This stage checks digest shape and path structure, not whether a digest
    identifies an authentic source receipt. Twin path provenance is trusted
    only as synthetic upstream input, never independently attested here.
    A missing path cannot be promoted to confirmed impact.
    """
    if not isinstance(incident, dict) or not isinstance(impact, dict):
        raise InvalidEvent("incident and impact must be objects")
    tenant, incident_id, service = (
        incident.get("tenant_id"), incident.get("incident_id"), incident.get("service_id"))
    if any(not isinstance(x, str) or not x for x in (tenant, incident_id, service)):
        raise InvalidEvent("invalid incident identity")
    if (impact.get("tenant_id") != tenant or impact.get("incident_id") != incident_id
            or impact.get("service_id") != service):
        raise InvalidEvent("impact identity mismatch")
    # Upstream synthetic evidence cannot be promoted into a LIVE attestation.
    for upstream in (incident, impact):
        if (upstream.get("runtime_attested") is not False
                or upstream.get("live_remediation_authorized") is not False):
            raise InvalidEvent("unqualified upstream runtime or live claim")
    events = incident.get("events")
    if not isinstance(events, list) or not events:
        raise InvalidEvent("missing incident events")
    evidence = set()
    incident_cis = set()
    for event in events:
        if not isinstance(event, dict) or event.get("tenant_id") != tenant or event.get("service_id") != service:
            raise InvalidEvent("invalid or cross-tenant event")
        digest = event.get("evidence_sha256")
        if not isinstance(digest, str) or not DIGEST.fullmatch(digest):
            raise InvalidEvent("invalid event evidence")
        evidence.add(digest)
        ci = event.get("ci_id")
        if not isinstance(ci, str) or not ci:
            raise InvalidEvent("invalid incident CI")
        incident_cis.add(ci)
    if type(impact.get("resource_budget_exhausted")) is not bool:
        raise InvalidEvent("unqualified impact resource budget")
    if impact["resource_budget_exhausted"] and (
            impact.get("impact_state") != "UNKNOWN" or impact.get("paths") != []):
        raise InvalidEvent("exhausted impact budget cannot support paths")
    paths = impact.get("paths")
    if not isinstance(paths, list):
        raise InvalidEvent("invalid impact paths")
    if impact.get("impact_state") not in ("UNKNOWN", "SOURCED_SYNTHETIC_PATH"):
        raise InvalidEvent("invalid impact state")
    if impact["impact_state"] == "UNKNOWN" and paths:
        raise InvalidEvent("UNKNOWN impact cannot have verified paths")
    path_evidence = set()
    for path in paths:
        if not isinstance(path, dict):
            raise InvalidEvent("invalid impact path")
        nodes, hashes = path.get("nodes"), path.get("evidence_sha256")
        if (not isinstance(nodes, list) or len(nodes) < 2 or
                not all(isinstance(n, str) and n for n in nodes) or
                nodes[0] not in incident_cis or nodes[-1] != service or
                len(set(nodes)) != len(nodes) or not isinstance(hashes, list) or
                len(hashes) != len(nodes) - 1 or
                not all(isinstance(h, str) and DIGEST.fullmatch(h) for h in hashes)):
            raise InvalidEvent("invalid impact path provenance")
        path_evidence.update(hashes)
    if impact["impact_state"] == "SOURCED_SYNTHETIC_PATH" and not paths:
        raise InvalidEvent("sourced impact requires a path")
    supported = bool(paths)
    cited = sorted(evidence | path_evidence)
    hypothesis = {
        "id": "synthetic-dependency-hypothesis",
        "claim": ("Synthetic source events may be related to the service through sourced dependencies"
                  if supported else "Service impact cannot be established from available dependencies"),
        "kind": "HYPOTHESIS_NOT_ROOT_CAUSE",
        "evidence_sha256": cited,
        "missing_evidence": [] if supported else ["SOURCED_DEPENDENCY_PATH"],
        "impact_state": impact["impact_state"],
    }
    # This membership check is internal consistency only, not independent\n    # verification of source authenticity or path-edge correspondence.
    available = evidence | path_evidence
    citations_valid = all(hash_ in available for hash_ in hypothesis["evidence_sha256"])
    critic = {
        "disposition": "SUPPORTED_SYNTHETIC_HYPOTHESIS" if supported and citations_valid else "NEEDS_MORE_EVIDENCE",
        "citations_valid": citations_valid,
        "root_cause_confirmed": False,
        "runtime_attested": False,
    }
    return {
        "schema": "aiops2.synthetic-analyst-critic.v1",
        "tenant_id": tenant,
        "incident_id": incident_id,
        "analyst": hypothesis,
        "critic": critic,
        "policy_disposition": "DENY_LIVE",
        "live_remediation_authorized": False,
        "runtime_attested": False,
    }
