"""Offline tests for Debian/GitHub candidate evidence join."""
import importlib.util
from pathlib import Path
import unittest

P = Path(__file__).resolve().parents[1] / "scripts" / "ops" / "join_debian_github_evidence.py"
spec = importlib.util.spec_from_file_location("join_debian_github_evidence", P)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def snapshot():
    return {"schema": "aiops2-debian-provenance-v1", "captured_at_utc": "2026-11-08T00:00:00Z",
            "containers": [{"name": "worker", "image_id": "sha256:abc",
                            "compose": {"com.docker.compose.project": "aiops2-metrics-cutover",
                                        "com.docker.compose.service": "worker"}}], "errors": []}


def manifest(candidate):
    return {"schema": "aiops2-component-candidates-v1", "candidates": [candidate]}


def candidate(**kwargs):
    return dict({"name": "Worker V28", "component": "worker", "github_sha": "fd347ec92a1c"}, **kwargs)


class JoinTests(unittest.TestCase):
    def test_no_image_claim_does_not_infer_from_names(self):
        result = m.assess(snapshot(), manifest(candidate()))
        self.assertEqual(result["candidates"][0]["runtime_match"], "NOT_ATTESTED")
        self.assertEqual(result["release_decision"], "HOLD")

    def test_exact_image_match_is_not_source_proof(self):
        result = m.assess(snapshot(), manifest(candidate(verified_runtime_image_id="sha256:abc")))
        item = result["candidates"][0]
        self.assertEqual(item["runtime_match"], "IMAGE_ID_MATCH_CLAIMED")
        self.assertEqual(item["matching_runtime_containers"][0]["compose_project"], "aiops2-metrics-cutover")
        self.assertEqual(item["source_to_image_provenance"], "NOT_INDEPENDENTLY_VERIFIED")
        self.assertEqual(item["decision"], "PRESERVE_AND_QUALIFY")

    def test_unmatched_image_does_not_claim_deployment(self):
        result = m.assess(snapshot(), manifest(candidate(verified_runtime_image_id="sha256:def")))
        self.assertEqual(result["candidates"][0]["runtime_match"], "NOT_ATTESTED")

    def test_invalid_claim_refused(self):
        with self.assertRaisesRegex(ValueError, "sha256"):
            m.assess(snapshot(), manifest(candidate(verified_runtime_image_id="worker:latest")))

    def test_duplicate_candidates_refused(self):
        c = candidate()
        with self.assertRaisesRegex(ValueError, "duplicate"):
            m.assess(snapshot(), {"schema": "aiops2-component-candidates-v1", "candidates": [c, c]})

    def test_wrong_schema_refused(self):
        with self.assertRaisesRegex(ValueError, "snapshot"):
            m.assess({"schema": "other"}, manifest(candidate()))


if __name__ == "__main__":
    unittest.main()
