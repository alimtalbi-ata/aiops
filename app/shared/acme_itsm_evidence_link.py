"""Presentation-only ACME Run/Evidence/ITSM join, adapted from the 2026-10-27
portal.acme_itsm_correlation contract. No I/O, GLPI API, tenant ACL or attestation.

Call only with snapshots fetched by existing authorized server-side readers.
Never expose a Core credential or promote a signed NOC ticket claim to a GLPI ticket.
"""
import re
from datetime import datetime, timedelta, timezone
from shared.tenant_scope import reject_unqualified_tenant_scope

_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\Z")
_SHA = re.compile(r"[a-f0-9]{64}\Z")
_SOURCE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z")
_MODES = frozenset({"DEMO", "REPLAY", "STORY"})
_SCHEMA = "aiops.acme-itsm-evidence-link.v1"


def _id(value):
    return isinstance(value, str) and _ID.fullmatch(value) is not None


def _ids(value):
    # Portal ledger permits a historical Analysis or Critique with zero
    # citations. The nonempty Run-wide Evidence union is checked below.
    if not isinstance(value, list) or len(value) > 80 or not all(_id(x) for x in value):
        raise ValueError("invalid evidence IDs")
    if len(value) != len(set(value)):
        raise ValueError("duplicate evidence IDs")
    return set(value)


def project_itsm_evidence(core_detail, ledger, signed_noc=None):
    """Join canonical IDs only; never verify GLPI or qualify tenant/runtime."""
    result = {
        "schema": _SCHEMA, "state": "UNKNOWN", "run_id": None,
        "incident_id": None, "analysis_ids": [], "critique_ids": [],
        "policy_decision_ids": [], "evidence_ids": [], "evidence_refs": [],
        "evidence_source_contract": None, "glpi_ticket_claim": None,
        "ticket_id": None, "ticket_verification": "NOT_TESTED_NO_GLPI_API_READ",
        "classification": "UNKNOWN", "tenant_acl_qualified": False,
        "runtime_attested": False, "effect_applied": False,
        "live_remediation_authorized": False,
    }
    try:
        if not isinstance(core_detail, dict) or not isinstance(ledger, dict):
            return result
        run = core_detail.get("run")
        if not isinstance(run, dict):
            return result
        rid, incident, mode = run.get("run_id"), run.get("incident_id"), run.get("mode")
        if not _id(rid) or not _id(incident) or mode not in _MODES:
            return result
        if (ledger.get("schema") != "aiops.demo-ledger-read.v1"
                or ledger.get("run_id") != rid or ledger.get("mode") != mode
                or ledger.get("classification") != "DEMO_CORE_RECORDED_NOT_LIVE"
                or ledger.get("source") != "CORE_AI_LEDGER_INTERNAL_READ"
                or ledger.get("evidence_classification") != "SYNTHETIC_ONLY"
                or ledger.get("tenant_acl_qualified") is not False
                or ledger.get("runtime_attested") is not False
                or ledger.get("event_link_verified") is not True):
            return result
        refs = ledger.get("evidence_refs")
        analyses, critiques, policies = (ledger.get(k) for k in
                                       ("analyses", "critiques", "policy_decisions"))
        if (not isinstance(refs, list) or not 1 <= len(refs) <= 80
                or not isinstance(analyses, list) or not 1 <= len(analyses) <= 50
                or not isinstance(critiques, list) or not 1 <= len(critiques) <= 50
                or not isinstance(policies, list) or len(policies) > 50):
            return result
        # A pure join cannot authorize tenant-scoped snapshots. The Portal
        # envelope explicitly includes a false top-level qualification flag;
        # scan everything else, including nested claims and the NOC source.
        reject_unqualified_tenant_scope(core_detail)
        reject_unqualified_tenant_scope({
            key: value for key, value in ledger.items()
            if key != "tenant_acl_qualified"
        })
        if signed_noc is not None:
            reject_unqualified_tenant_scope(signed_noc)
        evidence = {}
        for item in refs:
            if (not isinstance(item, dict)
                    or set(item) != {"evidence_id", "source", "payload_sha256", "known_at"}
                    or not _id(item.get("evidence_id"))
                    or not isinstance(item.get("source"), str)
                    or _SOURCE.fullmatch(item["source"]) is None
                    or not isinstance(item.get("known_at"), str)
                    or len(item["known_at"]) > 48
                    or not isinstance(item.get("payload_sha256"), str)
                    or _SHA.fullmatch(item["payload_sha256"]) is None
                    or item["evidence_id"] in evidence):
                return result
            try:
                known = datetime.fromisoformat(item["known_at"])
                if (known.tzinfo is None or known.utcoffset() is None
                        or known.astimezone(timezone.utc) >
                        datetime.now(timezone.utc) + timedelta(minutes=5)):
                    return result
            except (ValueError, OverflowError):
                # UTC normalization can overflow at year 1/9999 with offsets.
                # An unnormalizable ledger reference cannot be correlated.
                return result
            evidence[item["evidence_id"]] = item
        analysis_map = {}
        for a in analyses:
            if not isinstance(a, dict) or not _id(a.get("analysis_id")) or a["analysis_id"] in analysis_map:
                return result
            analysis_map[a["analysis_id"]] = _ids(a.get("evidence_ids"))
        critique_map = {}
        for c in critiques:
            if (not isinstance(c, dict) or not _id(c.get("critique_id"))
                    or c["critique_id"] in critique_map or c.get("analysis_id") not in analysis_map):
                return result
            if not _ids(c.get("evidence_ids")).issubset(analysis_map[c["analysis_id"]]):
                return result
            critique_map[c["critique_id"]] = c["analysis_id"]
        if set(evidence) != set().union(*analysis_map.values()):
            return result
        policy_ids = set()
        for p in policies:
            if (not isinstance(p, dict) or not _id(p.get("policy_decision_id"))
                    or p["policy_decision_id"] in policy_ids):
                return result
            aid, cid = p.get("analysis_id"), p.get("critique_id")
            if (aid is not None and aid not in analysis_map) or (cid is not None and cid not in critique_map):
                return result
            if aid is None and cid is None:
                return result
            if aid is not None and cid is not None and critique_map[cid] != aid:
                return result
            policy_ids.add(p["policy_decision_id"])
    except (ValueError, TypeError, KeyError):
        return result
    result.update({"state": "CORRELATED_UNATTESTED", "run_id": rid,
                   "incident_id": incident, "analysis_ids": sorted(analysis_map),
                   "critique_ids": sorted(critique_map),
                   "policy_decision_ids": sorted(policy_ids),
                   "evidence_ids": sorted(evidence),
                   # Copy only the four already-qualified Core reference fields;
                   # never expose raw payloads or infer observed metrics.
                   "evidence_refs": [evidence[key].copy() for key in sorted(evidence)],
                   "evidence_source_contract": "CORE_AI_LEDGER_INTERNAL_READ",
                   "classification": "SYNTHETIC_ONLY"})
    # Reuse the old signed-NOC contract: a claim is not a GLPI API read.
    if (isinstance(signed_noc, dict)
            and signed_noc.get("schema") == "aiops.noc-runtime-envelope.v1"
            and signed_noc.get("source_mode") == "ALLOWLISTED_HMAC_SIGNED_READ_MODEL"
            and signed_noc.get("provenance") == "AUTHENTICATED_SOURCE_PAYLOAD_NOT_RUNTIME_ATTESTATION"
            and signed_noc.get("production_qualified") is False
            and signed_noc.get("ticket_provenance") == "UPSTREAM_SIGNED_CLAIM"
            and signed_noc.get("run_id") == rid
            and signed_noc.get("incident_id") == incident
            and signed_noc.get("source_payload_authenticated") is True
            and signed_noc.get("source_authentication") == "HMAC_SHA256_VERIFIED"
            and signed_noc.get("runtime_attested") is False
            and signed_noc.get("live_remediation_authorized") is False
            and isinstance(signed_noc.get("source_payload_sha256"), str)
            and _SHA.fullmatch(signed_noc["source_payload_sha256"]) is not None):
        claim = signed_noc.get("ticket_id")
        if _id(claim) and not claim.startswith("SIM-"):
            result["glpi_ticket_claim"] = claim
    return result
