"""Read-only, fail-closed presentation of E2E lineage readiness.

Consumes only the result of project_lineage(), never raw client assertions.
"""
from collections.abc import Mapping

REQUIRED = ("source", "core", "evidence", "critic", "policy", "temporal", "worker", "itsm")


def summarize_lineage(projection):
    if not isinstance(projection, Mapping) or projection.get("read_only") is not True:
        raise ValueError("authenticated read-only projection required")
    stages = projection.get("stages")
    stages = stages if isinstance(stages, Mapping) else {}
    statuses = {}
    for name in REQUIRED:
        entry = stages.get(name)
        entry = entry if isinstance(entry, Mapping) else {}
        status = entry.get("status")
        evidence = entry.get("evidence_ref")
        statuses[name] = status if status in ("PASS", "FAIL", "BLOCKED", "UNKNOWN", "NOT_APPLICABLE") and (status != "PASS" or isinstance(evidence, str) and bool(evidence.strip())) else "UNKNOWN"
    passed = sum(s == "PASS" for s in statuses.values())
    blockers = [name for name, status in statuses.items() if status != "PASS"]
    questions = [
        {"stage": name, "question": f"Quelle preuve backend authentifiée permet de qualifier {name} ?"}
        for name in blockers
    ]
    return {"verified_pass_count": passed, "required_count": len(REQUIRED),
            "coverage_percent": round(100 * passed / len(REQUIRED)),
            "ready": False,  # Read-only receipts never authorize readiness for LIVE actions.
            "status": "EVIDENCE_COMPLETE_NOT_APPROVED" if not blockers else "INCOMPLETE",
            "unqualified_stages": blockers, "human_questions": questions,
            "approval": "UNVERIFIED", "resolution": "UNVERIFIED", "read_only": True}
