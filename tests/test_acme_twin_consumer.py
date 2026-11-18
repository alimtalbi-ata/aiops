import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))
from portal.acme_twin_provenance import build_twin_evidence
from portal.acme_twin_consumer import project_twin_consumer


class TwinConsumerTests(unittest.TestCase):
    def setUp(self):
        t = build_twin_evidence((ROOT / "app/portal/acme-fixtures.json").read_bytes())
        self.model = {k: t[k] for k in ("source_sha256", "run_id", "incident_id", "impact_incident_id")}
        self.model.update({k: t["impact"][k] for k in ("impact_path", "affected_ci_ids")})
        self.model.update(ci_count=len(t["nodes"]), twin_evidence=t)

    def test_multipath_and_unknown_freshness(self):
        v = project_twin_consumer(self.model)
        self.assertEqual(v["structural_impact"]["target_path_count"], 2)
        self.assertEqual(v["structural_impact"]["path_count_by_ci"]["VM-PAY-01"], 2)
        self.assertEqual(len(v["hypothesis_citations"]), 5)
        self.assertEqual(v["freshness"], {"status": "UNKNOWN", "observed_at": None, "age_seconds": None, "reason": "NO_RUNTIME_OBSERVATION"})
        self.assertFalse(v["runtime_attested"])
        self.assertEqual(v["binding"]["binding_status"], "UNBOUND")

    def test_identity_and_authority_rejections(self):
        for key, value in (("tenant_id", " acme "), ("attempt_id", "attempt-1"), ("core_run_id", "core-1"), ("freshness", "FRESH"), ("observed_at", "2026-11-18T12:00:00Z"), ("runtime_attested", True), ("source_sha256", "0" * 64)):
            with self.subTest(key=key):
                m = copy.deepcopy(self.model)
                m["twin_evidence"][key] = value
                with self.assertRaises(ValueError):
                    project_twin_consumer(m)

    def test_edge_and_provenance_rejections(self):
        for key, value in (("target_id", "MISSING"), ("relation_type", "HEALTHY")):
            m = copy.deepcopy(self.model)
            m["twin_evidence"]["edges"][0][key] = value
            with self.assertRaises(ValueError):
                project_twin_consumer(m)
        self.model["twin_evidence"]["edges"][0]["provenance"]["source_sha256"] = "0" * 64
        with self.assertRaises(ValueError):
            project_twin_consumer(self.model)

    def test_missing_and_disconnected_rejected(self):
        m = copy.deepcopy(self.model)
        del m["twin_evidence"]
        with self.assertRaises(ValueError):
            project_twin_consumer(m)
        self.model["twin_evidence"]["edges"].pop(0)
        with self.assertRaises(ValueError):
            project_twin_consumer(self.model)

    def test_no_mutation_and_deterministic(self):
        before = copy.deepcopy(self.model)
        a = project_twin_consumer(self.model)
        b = project_twin_consumer(self.model)
        self.assertEqual(a, b)
        self.assertEqual(before, self.model)
        a["hypothesis_citations"][0]["freshness"] = "FRESH"
        self.assertEqual(before, self.model)
