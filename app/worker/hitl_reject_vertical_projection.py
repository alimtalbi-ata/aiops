"""Read-only Worker projection of a synthetic Core HITL REJECT vertical slice.

This is NOT a new ledger, Portal endpoint, human approval, or executor.
Only a fully bound Core/PG16 fixture may be projected. REJECT vetoes even
a Policy SIMULATE recommendation; verification/reopen remain advisory.
"""
import re

_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
_STAGES = (
    ("DGX_ANALYST", "ANALYST_RECORDED", "analysis_id"),
    ("DGX_CRITIC", "CRITIC_RECORDED", "critique_id"),
    ("POLICY", "POLICY_EVALUATED", "proposal_id"),
    ("HITL", "HUMAN_REJECT_SYNTHETIC", "approval_id"),
    ("REMEDIATE", "SIMULATE_SUPPRESSED", "proposal_id"),
    ("VERIFY", "VERIFY_UNRESOLVED", "proposal_id"),
)


class UnqualifiedRejectStory(ValueError):
    """Missing, stale, forged or effect-capable Core correlation."""


def _require(condition, reason):
    if not condition:
        raise UnqualifiedRejectStory(reason)


def project_rejected_simulation(core_view, ledger, policy_verdict):
    """Correlate existing Core readback and immutable fixture references.

    Caller is responsible for authenticating the Core source and PG16 readback.
    No temporal signal, effect, Core write or human identity is created here.
    """
    _require(all(isinstance(x, dict) for x in
                 (core_view, ledger, policy_verdict)), "invalid_input")
    run = core_view.get("run")
    _require(isinstance(run, dict), "run_missing")
    for key in ("tenant_id", "incident_id", "run_id", "analysis_id",
                "critique_id", "proposal_id", "approval_id", "event_id",
                "evidence_id"):
        _require(type(ledger.get(key)) is str and bool(ledger[key]),
                 "missing_" + key)
    _require(run.get("run_id") == ledger["run_id"]
             and run.get("incident_id") == ledger["incident_id"]
             and run.get("mode") in ("DEMO", "REPLAY", "STORY")
             and run.get("status") == "BLOCKED",
             "core_run_not_blocked_synthetic")
    _require(ledger.get("incident_state") == "OPEN"
             and ledger.get("synthetic") is True
             and ledger.get("tenant_provenance") == "CI_SIGNED_PROOF_ONLY"
             and ledger.get("actor_identity") == "SYNTHETIC_UNVERIFIED"
             and ledger.get("identity_attested") is False,
             "tenant_or_identity_not_qualified")
    _require(ledger.get("analysis_status") == "VALID"
             and ledger.get("critic_validated") is True
             and ledger.get("proposal_status") == "REJECTED"
             and ledger.get("approval_decision") == "REJECT"
             and ledger.get("outbox_decision") == "REJECT"
             and ledger.get("terminal_status") == "DEAD"
             and ledger.get("terminal_audit_rows") == 1,
             "ledger_reject_binding_missing")
    _require(type(ledger.get("proposal_revision")) is int
             and ledger["proposal_revision"] >= 1
             and isinstance(ledger.get("proposal_hash"), str)
             and _DIGEST.fullmatch(ledger["proposal_hash"]) is not None
             and isinstance(ledger.get("terminal_receipt_sha256"), str)
             and _DIGEST.fullmatch(ledger["terminal_receipt_sha256"]) is not None,
             "hash_revision_unqualified")
    _require(policy_verdict.get("state") == "PASS"
             and policy_verdict.get("decision") == "SIMULATE"
             and policy_verdict.get("execution_allowed") is False
             and policy_verdict.get("effect_allowed") is False,
             "policy_effect_or_unknown")
    events = core_view.get("events")
    gates = core_view.get("gates")
    _require(isinstance(events, list) and isinstance(gates, list),
             "core_events_missing")
    matching = []
    for stage, event_type, binding in _STAGES:
        found = [e for e in events if isinstance(e, dict)
                 and e.get("stage") == stage and e.get("event_type") == event_type]
        _require(len(found) == 1, "missing_or_duplicate_" + stage)
        e = found[0]
        payload = e.get("payload")
        _require(isinstance(payload, dict)
                 and payload.get(binding) == ledger[binding]
                 and payload.get("tenant_id") == ledger["tenant_id"]
                 and payload.get("run_id") == ledger["run_id"]
                 and payload.get("execution_allowed") is False
                 and payload.get("effect_allowed") is False
                 and ledger["evidence_id"] in e.get("evidence_ids", []),
                 "unbound_" + stage)
        matching.append(e)
    _require(all(type(e.get("sequence")) is int for e in matching)
             and [e["sequence"] for e in matching]
             == sorted({e["sequence"] for e in matching}),
             "event_sequence_unqualified")
    _require(not any(e.get("decision") == "APPROVE"
                     or e.get("event_type") in ("EXECUTED", "EFFECT_COMMITTED")
                     for e in events if isinstance(e, dict)),
             "approval_or_effect_event")
    analyst, critic, policy, hitl, remediate, verify = matching
    _require(analyst.get("status") == "PASS"
             and critic.get("status") == "PASS"
             and policy.get("decision") == "SIMULATE"
             and hitl.get("decision") == "REJECT"
             and hitl.get("status") == "BLOCKED"
             and remediate.get("status") == "BLOCKED"
             and remediate["payload"].get("simulation_executed") is False
             and verify.get("status") == "BLOCKED"
             and verify["payload"].get("resolution_verified") is False
             and verify["payload"].get("reopen_recommended") is True,
             "reject_not_vetoing_simulation")
    _require(len([g for g in gates if isinstance(g, dict)
                  and g.get("stage") == "POLICY"
                  and g.get("state") == "PASS"
                  and g.get("decision") == "SIMULATE"]) == 1,
             "policy_gate_unqualified")
    return {
        "schema": "aiops.worker-reject-simulate-verification.v1",
        "data_classification": "CI_SYNTHETIC_READ_ONLY",
        "tenant_id": ledger["tenant_id"],
        "incident_id": ledger["incident_id"],
        "run_id": ledger["run_id"],
        "analysis_id": ledger["analysis_id"],
        "critique_id": ledger["critique_id"],
        "proposal_id": ledger["proposal_id"],
        "proposal_revision": ledger["proposal_revision"],
        "approval_id": ledger["approval_id"],
        "reject_event_id": ledger["event_id"],
        "evidence_id": ledger["evidence_id"],
        "terminal_receipt_sha256": ledger["terminal_receipt_sha256"],
        "policy_decision": "SIMULATE",
        "human_decision": "REJECT_SYNTHETIC_UNVERIFIED",
        "simulation_status": "SUPPRESSED_BY_REJECT",
        "verification_status": "UNVERIFIED",
        "reopen_status": "RECOMMENDED_NOT_EXECUTED",
        "incident_state": "OPEN",
        "run_status": "BLOCKED",
        "portal_projection": "CORRELATED_IDS_ONLY_NOT_TENANT_AUTHORIZED",
        "oidc_glpi_human_identity": "NOT_ATTESTED",
        "execution_allowed": False,
        "effect_allowed": False,
    }
