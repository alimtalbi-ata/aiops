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
    verified = []
    seen_refs = set()
    for r in refs:
        if not isinstance(r, Mapping) or r.get("verification") != "VERIFIED":
            continue
        system, external_id, evidence = r.get("system"), r.get("id"), r.get("evidence_ref")
        # A visible GLPI ticket or an empty/boolean identifier is not a Core xref.
        if not isinstance(system, str) or not system.strip():
            continue
        if isinstance(external_id, bool) or not isinstance(external_id, (str, int)):
            continue
        if not str(external_id).strip() or not isinstance(evidence, str) or not evidence.strip():
            continue
        key = (system.strip(), str(external_id).strip())
        if key in seen_refs:
            continue
        seen_refs.add(key)
        verified.append({"system": key[0], "id": key[1], "evidence_ref": evidence.strip()})
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
