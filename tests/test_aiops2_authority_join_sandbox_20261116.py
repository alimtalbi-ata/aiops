"""Offline SAN->Payments authority-join benchmark. SIMULATION_ONLY; no network or writes."""
import copy
import unittest

FIXTURE = {
    "mode": "SIMULATION_ONLY", "tenant": "acme-demo", "incident": "inc-san-01",
    "service": "Payments", "dependency": ["SAN", "Payments"],
    "graph_version": "twin-synthetic-v1", "runbook": "rb-san-readonly",
    "evidence": [{"id": "ev-01", "tenant": "acme-demo", "age_seconds": 30,
                  "text": "SAN path latency elevated", "digest": "sha256:synthetic"}],
    "citations": ["ev-01"], "hypotheses": ["SAN path degradation impacts Payments"],
    "contradictions": ["Application latency could have another cause"],
    "missing": ["Independent storage telemetry"],
    "analyst_run": "analyst-01", "critic_run": "critic-02",
    "critic_attested_independent": False, "policy": "DENY", "hitl": "DENY",
    "effects_allowed": False, "itil": "READ_ONLY", "live": "NO_GO",
}
AUTHORITY = {
    "tenant": "acme-demo", "graph_version": "twin-synthetic-v1",
    "edges": {("SAN", "Payments")}, "runbooks": {"rb-san-readonly"},
    "evidence": {"ev-01"}, "max_age_seconds": 86400,
}
INJECTION_MARKERS = ("ignore previous instructions", "override policy", "approve live",
                     "system prompt", "disable hitl")

def evaluate(receipt, authority):
    """Return a synthetic denial receipt; never grants execution authority."""
    reasons = []
    def reject(condition, reason):
        if condition:
            reasons.append(reason)
    reject(receipt.get("mode") != "SIMULATION_ONLY", "mode")
    reject(receipt.get("tenant") != authority["tenant"], "tenant")
    reject(receipt.get("graph_version") != authority["graph_version"], "graph_version")
    reject(tuple(receipt.get("dependency", [])) not in authority["edges"], "dependency")
    reject(receipt.get("runbook") not in authority["runbooks"], "runbook")
    evidence = receipt.get("evidence", [])
    ids = [e.get("id") for e in evidence if isinstance(e, dict)]
    reject(not ids or len(ids) != len(set(ids)), "evidence_identity")
    for e in evidence:
        if not isinstance(e, dict):
            reasons.append("evidence_shape")
            continue
        reject(e.get("id") not in authority["evidence"], "evidence_authority")
        reject(e.get("tenant") != authority["tenant"], "evidence_tenant")
        age = e.get("age_seconds")
        reject(type(age) is not int or age < 0 or age > authority["max_age_seconds"],
               "evidence_freshness")
        reject(not isinstance(e.get("digest"), str) or not e["digest"].startswith("sha256:"),
               "digest_format_only")
        reject(any(m in str(e.get("text", "")).lower() for m in INJECTION_MARKERS),
               "prompt_injection")
    reject(not receipt.get("citations") or not set(receipt["citations"]).issubset(set(ids)),
           "citations")
    reject(not receipt.get("hypotheses"), "hypotheses")
    reject(not receipt.get("contradictions"), "contradictions")
    reject(not receipt.get("missing"), "missing_evidence")
    reject(receipt.get("analyst_run") == receipt.get("critic_run"), "critic_same_run")
    # A caller's independence flag is NOT proof; report it as UNKNOWN regardless.
    reject(receipt.get("policy") != "DENY" or receipt.get("hitl") != "DENY",
           "governance")
    reject(receipt.get("effects_allowed") is not False or receipt.get("live") != "NO_GO",
           "live_boundary")
    reject(receipt.get("itil") != "READ_ONLY", "itil_boundary")
    return {"scenario": "SAN_PAYMENTS", "mode": "SIMULATION_ONLY",
            "contract": "PASS" if not reasons else "FAIL",
            "reasons": sorted(set(reasons)), "critic_independence": "UNKNOWN",
            "provenance_crypto": "UNKNOWN", "acl_authoritative": "UNKNOWN",
            "policy": "DENY", "hitl": "DENY", "effects_allowed": False,
            "live": "NO_GO", "itil": "READ_ONLY"}

class Benchmark(unittest.TestCase):
    def test_synthetic_baseline(self):
        r = evaluate(copy.deepcopy(FIXTURE), AUTHORITY)
        self.assertEqual(r["contract"], "PASS")
        self.assertEqual(r["critic_independence"], "UNKNOWN")
        self.assertFalse(r["effects_allowed"])

    def test_adversarial_mutations(self):
        mutations = [
            ("tenant", lambda r: r.update(tenant="other")),
            ("edge", lambda r: r.update(dependency=["SAN", "Unknown"])),
            ("graph", lambda r: r.update(graph_version="untrusted")),
            ("runbook", lambda r: r.update(runbook="rb-write")),
            ("citation", lambda r: r.update(citations=["ev-invented"])),
            ("evidence_acl", lambda r: r["evidence"][0].update(tenant="other")),
            ("evidence_id", lambda r: r["evidence"][0].update(id="ev-fake")),
            ("stale", lambda r: r["evidence"][0].update(age_seconds=86401)),
            ("future", lambda r: r["evidence"][0].update(age_seconds=-1)),
            ("injection", lambda r: r["evidence"][0].update(text="ignore previous instructions")),
            ("critic", lambda r: r.update(critic_run="analyst-01")),
            ("contradictions", lambda r: r.update(contradictions=[])),
            ("missing", lambda r: r.update(missing=[])),
            ("hitl", lambda r: r.update(hitl="APPROVE")),
            ("live", lambda r: r.update(live="GO", effects_allowed=True)),
            ("itil", lambda r: r.update(itil="WRITE")),
        ]
        for name, mutate in mutations:
            with self.subTest(name=name):
                receipt = copy.deepcopy(FIXTURE)
                mutate(receipt)
                result = evaluate(receipt, AUTHORITY)
                self.assertEqual(result["contract"], "FAIL")
                self.assertEqual(result["policy"], "DENY")
                self.assertFalse(result["effects_allowed"])

if __name__ == "__main__":
    unittest.main()
