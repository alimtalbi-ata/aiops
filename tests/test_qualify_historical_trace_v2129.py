import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from tools.qualify_historical_trace_v2129 import qualify, read
from tools.verify_offline_manifest_v2128 import REQUIRED
from tools.summarize_core_historical_v2125 import EXPECTED_RUN


class TraceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.run = {"run": {"run_id": EXPECTED_RUN, "status": "BLOCKED", "mode": "DEMO"},
                    "events": [{"evidence_ids": ["E1"]}], "stages": []}
        self.ledger = {"run_id": EXPECTED_RUN,
                       "analyses": [{"evidence_ids": ["E1"]}],
                       "critiques": [{"evidence_ids": ["E1"], "validated": False}],
                       "policy_decisions": [{"state": "BLOCKED"}]}
        self.evidence = {"run_id": EXPECTED_RUN, "items": [{"evidence_id": "E1"}]}
        entries = []
        for name in sorted(REQUIRED):
            body = ("fixture:" + name).encode()
            (self.root / name).write_bytes(body)
            entries.append({"name": name, "sha256": hashlib.sha256(body).hexdigest()})
        self.manifest = {
            "version": "2.12.4", "mode": "OFFLINE_MIXED_SEPARATED",
            "historical_source": "OPERATOR_SUPPLIED_SUMMARY_NOT_INDEPENDENTLY_AUTHENTICATED",
            "dgx_independently_attested": False, "live_execution_qualified": False,
            "files": entries}
        self.save()

    def save(self):
        (self.root / "manifest.json").write_text(json.dumps(self.manifest))

    def check(self):
        return qualify(self.run, self.ledger, self.evidence, self.root)

    def reject(self):
        with self.assertRaises(ValueError):
            self.check()

    def test_positive(self):
        x = self.check()
        self.assertEqual(x["status"], "PASS")
        self.assertFalse(x["executor_fencing_qualified"])

    def test_missing_evidence(self):
        self.evidence["items"] = []
        self.reject()

    def test_unblocked_run(self):
        self.run["run"]["status"] = "COMPLETED"
        self.reject()

    def test_live_run(self):
        self.run["run"]["mode"] = "LIVE"
        self.reject()

    def test_unblocked_policy(self):
        self.ledger["policy_decisions"][0]["state"] = "APPROVED"
        self.reject()

    def test_absent_policy(self):
        self.ledger["policy_decisions"] = []
        self.reject()

    def test_mismatched_run(self):
        self.ledger["run_id"] = "OTHER"
        self.reject()

    def test_bad_provenance(self):
        self.manifest["historical_source"] = "DGX_INDEPENDENT"
        self.save()
        self.reject()

    def test_manifest_tampered(self):
        (self.root / "index.html").write_text("tampered")
        self.reject()

    def test_source_symlink(self):
        path = self.root / "source.json"
        path.symlink_to("/etc/hosts")
        with self.assertRaises(ValueError):
            read(path)


if __name__ == "__main__":
    unittest.main()
