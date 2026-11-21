"""Offline synthetic authority-join acceptance tests; no services or network used."""
import copy
import unittest

FIXTURE = {
    "mode": "SIMULATION_ONLY", "tenant": "acme-demo",
    "incident": {"id": "san-p1", "service": "san"},
    "dependency": {"from": "san", "to": "payments", "version": "twin-fixture-v1", "tenant": "acme-demo"},
    "evidence": [{"id": "ev-san", "tenant": "acme-demo", "observed_at": 1000, "source": "synthetic-monitor"}],
    "analysis": {"hypotheses": [{"text": "SAN path degradation affects Payments", "citations": ["ev-san"]}],
                 "contradictions": ["alternate Payments-side fault unexcluded"],
                 "missing": ["real switch telemetry"], "runbook": "rb-san-readonly"},
    "runbooks": [{"id": "rb-san-readonly", "tenant": "acme-demo", "approved": True}],
    "acl": {"tenant": "acme-demo", "actor": "demo-analyst", "allowed_evidence": ["ev-san"]},
    "critic": {"execution_id": "critic-fixture", "analyst_execution_id": "analyst-fixture",
               "independence_attested": False},
    "policy": "DENY", "hitl": "DENY", "effects_allowed": False,
    "itil": {"operation": "READ_ONLY", "external_write": False},
}

def assess(record, now=1100, max_age=300):
    """Return synthetic contract findings; never grant operational permission."""
    errors = []
    if record.get("mode") != "SIMULATION_ONLY":
        errors.append("mode")
    tenant = record.get("tenant")
    dep = record.get("dependency", {})
    if dep.get("tenant") != tenant or dep.get("from") != "san" or dep.get("to") != "payments" or not dep.get("version"):
        errors.append("dependency")
    acl = record.get("acl", {})
    if acl.get("tenant") != tenant or not acl.get("actor"):
        errors.append("acl")
    evidence = record.get("evidence", [])
    ids = set()
    for item in evidence:
        eid = item.get("id")
        if not eid or eid in ids or item.get("tenant") != tenant or eid not in acl.get("allowed_evidence", []):
            errors.append("evidence_acl")
        ids.add(eid)
        ts = item.get("observed_at")
        if not isinstance(ts, (int, float)) or not 0 <= now - ts <= max_age:
            errors.append("freshness")
        if not item.get("source"):
            errors.append("provenance")
    analysis = record.get("analysis", {})
    hypotheses = analysis.get("hypotheses", [])
    if not hypotheses or any(not h.get("text") or not h.get("citations") or
                             any(ref not in ids for ref in h.get("citations", [])) for h in hypotheses):
        errors.append("citations")
    if not analysis.get("contradictions") or not analysis.get("missing"):
        errors.append("uncertainty")
    rb = analysis.get("runbook")
    if not any(r.get("id") == rb and r.get("tenant") == tenant and r.get("approved") is True
               for r in record.get("runbooks", [])):
        errors.append("runbook")
    critic = record.get("critic", {})
    if not critic.get("execution_id") or critic.get("execution_id") == critic.get("analyst_execution_id"):
        errors.append("critic_identity")
    # Caller-provided independence metadata is NOT trusted as an authority.
    if record.get("policy") != "DENY" or record.get("hitl") != "DENY" or record.get("effects_allowed") is not False:
        errors.append("safety")
    itil = record.get("itil", {})
    if itil.get("operation") != "READ_ONLY" or itil.get("external_write") is not False:
        errors.append("itil")
    # Never claim verified critic independence or authorized execution from this fixture.
    return {"synthetic_contract_ok": not errors, "findings": sorted(set(errors)),
            "critic_independence": "UNKNOWN", "acl_authority": "UNKNOWN",
            "evidence_integrity": "UNKNOWN", "llm": "NOT_EXECUTED",
            "glpi": "NOT_EXECUTED", "temporal": "NOT_EXECUTED",
            "policy": "DENY", "hitl": "DENY", "effects_allowed": False, "live": "NO_GO"}

class OfflineAuthorityJoinTests(unittest.TestCase):
    def test_fixture_is_only_synthetic(self):
        receipt = assess(copy.deepcopy(FIXTURE))
        self.assertTrue(receipt["synthetic_contract_ok"])
        self.assertEqual(receipt["critic_independence"], "UNKNOWN")
        self.assertFalse(receipt["effects_allowed"])

    def test_negative_matrix(self):
        mutations = {
            "live": lambda r: r.update(mode="LIVE"),
            "cross_tenant_dep": lambda r: r["dependency"].update(tenant="other"),
            "missing_graph_version": lambda r: r["dependency"].update(version=""),
            "cross_tenant_evidence": lambda r: r["evidence"][0].update(tenant="other"),
            "stale": lambda r: r["evidence"][0].update(observed_at=1),
            "future": lambda r: r["evidence"][0].update(observed_at=1200),
            "missing_source": lambda r: r["evidence"][0].update(source=""),
            "acl_denied": lambda r: r["acl"].update(allowed_evidence=[]),
            "invented_citation": lambda r: r["analysis"]["hypotheses"][0].update(citations=["fabricated"]),
            "no_contradictions": lambda r: r["analysis"].update(contradictions=[]),
            "no_missing": lambda r: r["analysis"].update(missing=[]),
            "unknown_runbook": lambda r: r["analysis"].update(runbook="unknown"),
            "cross_tenant_runbook": lambda r: r["runbooks"][0].update(tenant="other"),
            "same_critic": lambda r: r["critic"].update(execution_id="analyst-fixture"),
            "hitl_allow": lambda r: r.update(hitl="ALLOW"),
            "policy_allow": lambda r: r.update(policy="ALLOW"),
            "effect": lambda r: r.update(effects_allowed=True),
            "itil_write": lambda r: r["itil"].update(external_write=True),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                r = copy.deepcopy(FIXTURE)
                mutate(r)
                receipt = assess(r)
                self.assertFalse(receipt["synthetic_contract_ok"])
                self.assertTrue(receipt["findings"])
                self.assertFalse(receipt["effects_allowed"])
                self.assertEqual(receipt["live"], "NO_GO")

if __name__ == "__main__":
    unittest.main()
