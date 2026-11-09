"""Pure fail-closed Analyst/Critic/Policy handoff; no IO or dispatch."""
from hashlib import sha256
import json
import re

def evaluate_handoff(observation_receipt, analyst, critic, policy, *, run_id, ticket_id, tenant_id):
    def result(reason, digest=None):
        return {"status": "UNKNOWN" if reason != "READ_ONLY_APPROVED" else "READY_FOR_EVIDENCE",
                "reason": reason, "digest": digest, "dispatch_allowed": False}
    if not isinstance(observation_receipt, dict) or observation_receipt.get("status") != "ACCEPTED" or not isinstance(observation_receipt.get("fingerprint"), str) or re.fullmatch(r"[0-9a-f]{64}", observation_receipt["fingerprint"]) is None:
        return result("OBSERVATION_UNVERIFIED")
    if not isinstance(run_id, str) or not run_id.strip() or not isinstance(tenant_id, str) or not tenant_id.strip() or type(ticket_id) is not int or ticket_id <= 0:
        return result("INVALID_IDENTITY")
    if any(type(observation_receipt.get(k)) is not type(v) or observation_receipt.get(k) != v
           for k, v in (("run_id", run_id), ("tenant_id", tenant_id), ("ticket_id", ticket_id))):
        return result("OBSERVATION_IDENTITY_MISMATCH")
    for name, stage in (("ANALYST", analyst), ("CRITIC", critic), ("POLICY", policy)):
        if not isinstance(stage, dict):
            return result(name + "_MISSING")
        if any(stage.get(k) != v or type(stage.get(k)) is not type(v) for k,v in (("run_id",run_id),("ticket_id",ticket_id),("tenant_id",tenant_id),("observation_fingerprint",observation_receipt["fingerprint"]))):
            return result(name + "_IDENTITY_MISMATCH")
        if stage.get("status") != "PASS" or stage.get("unknown") is not False:
            return result(name + "_DENIED_OR_UNKNOWN")
    if analyst.get("evidence_sufficient") is not True:
        return result("ANALYST_INSUFFICIENT")
    if critic.get("approved") is not True or policy.get("allowed_mode") != "OBSERVE":
        return result("CRITIC_OR_POLICY_REFUSED")
    canonical = {"run_id":run_id,"ticket_id":ticket_id,"tenant_id":tenant_id,"observation_fingerprint":observation_receipt["fingerprint"],"analyst":analyst,"critic":critic,"policy":policy}
    try:
        digest = sha256(json.dumps(canonical, sort_keys=True, separators=(",",":"), allow_nan=False).encode()).hexdigest()
    except (ValueError, TypeError, OverflowError, RecursionError):
        return result("NONCANONICAL_HANDOFF")
    return result("READ_ONLY_APPROVED",digest)
