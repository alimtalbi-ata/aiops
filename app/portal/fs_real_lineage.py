"""Read-only, fail-closed Portal projection of authenticated backend receipts.

No network requests, ticket writes, approvals or resolution transitions.
"""
from collections.abc import Mapping

STAGES = ("source", "core", "evidence", "critic", "policy", "temporal", "worker", "itsm")
STATES = {"PASS", "FAIL", "BLOCKED", "UNKNOWN", "NOT_APPLICABLE"}


def project_lineage(receipt):
    if not isinstance(receipt, Mapping):
        raise TypeError("receipt must be a mapping")
    raw = receipt.get("stages")
    raw = raw if isinstance(raw, Mapping) else {}
    stages = {}
    for name in STAGES:
        entry = raw.get(name)
        entry = entry if isinstance(entry, Mapping) else {}
        ref = entry.get("evidence_ref")
        ref = ref if isinstance(ref, str) and ref.strip() else None
        status = entry.get("status")
        if status not in STATES or (status == "PASS" and not ref):
            status = "UNKNOWN"
        stages[name] = {"status": status, "evidence_ref": ref}
    refs = receipt.get("external_refs")
    refs = refs if isinstance(refs, list) else []
    verified = [
        {"system": r["system"], "id": str(r["id"]), "evidence_ref": r["evidence_ref"]}
        for r in refs if isinstance(r, Mapping)
        and r.get("verification") == "VERIFIED"
        and isinstance(r.get("system"), str)
        and isinstance(r.get("id"), (str, int))
        and isinstance(r.get("evidence_ref"), str) and r["evidence_ref"].strip()
    ]
    if not verified:
        stages["itsm"] = {"status": "UNKNOWN", "evidence_ref": None}
    return {
        "scenario": str(receipt.get("scenario") or "UNKNOWN"),
        "incident_id": receipt.get("incident_id"),
        "run_id": receipt.get("run_id"),
        "stages": stages,
        "verified_external_refs": verified,
        "approval": "UNVERIFIED",
        "resolution": "UNVERIFIED",
        "read_only": True,
    }
