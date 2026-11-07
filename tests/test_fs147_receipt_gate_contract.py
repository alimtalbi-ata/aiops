"""FS147 receipt schema regressions: synthetic fixtures, never host/HITL proof."""
import importlib.util
import pathlib
import unittest

SOURCE = pathlib.Path(__file__).resolve().parents[1] / "scripts/fs/fs147_receipt_gate.py"
spec = importlib.util.spec_from_file_location("fs147_receipt_gate", SOURCE)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


def synthetic_receipt():
    # Synthetic contract-only fixture; no URLs are independently verified.
    run = "SYNTHETIC-RUN-DO-NOT-DEPLOY"
    stages = {
        name: {"status": "VERIFIED", "proof_url": "https://example.invalid/not-proof",
               "run_id": run}
        for name in gate.STAGES
    }
    stages["hitl_native"].update(
        ticket_id=147, alert_fingerprint="SYNTHETIC-FP",
        action="SYNTHETIC-ACTION", path="/fs-lab",
        expires_at="2099-01-01T00:00:00Z", validator_id="SYNTHETIC-VALIDATOR",
        approval_id="SYNTHETIC-APPROVAL"
    )
    stages["safe_resume"]["approval_id"] = "SYNTHETIC-APPROVAL"
    return dict(alert_fingerprint="SYNTHETIC-FP", incident_id="SYNTHETIC-INC",
                run_id=run, evidence_id="SYNTHETIC-EVD", glpi_ticket_id=147,
                scenario="AIOPS2-REAL-FS-20261106", mode="DEMO", stages=stages)


class ReceiptFailClosedTests(unittest.TestCase):
    def test_placeholder_and_local_proof_urls_rejected(self):
        for url in (
            "https://example.invalid/not-proof",
            "https://example.com/placeholder",
            "http://evidence.example.org/run",
            "https://localhost/run",
            "https://127.0.0.1/run",
            "https://user:password@evidence.example.org/run",
            "https://evidence.example.org/run#unverified",
            "https://evidence.example.org:8443/run",
        ):
            with self.subTest(url=url):
                r = synthetic_receipt()
                r["stages"]["prometheus"]["proof_url"] = url
                self.assertIn("missing proof URL prometheus", gate.validate(r))

    def test_ip_literal_proof_hosts_rejected(self):
        # No network calls: reject internal/metadata and public IP literals.
        for url in (
            "https://169.254.169.254/latest/meta-data/",
            "https://10.0.0.5/run",
            "https://172.16.1.2/run",
            "https://192.168.1.1/run",
            "https://8.8.8.8/run",
            "https://[::1]/run",
            "https://[fd00::1]/run",
        ):
            with self.subTest(url=url):
                self.assertFalse(gate.proof_url_is_reviewable(url))
                r = synthetic_receipt()
                r["stages"]["prometheus"]["proof_url"] = url
                self.assertIn("missing proof URL prometheus", gate.validate(r))

    def test_https_reviewable_url_still_requires_independent_review(self):
        self.assertTrue(gate.proof_url_is_reviewable(
            "https://github.com/alimtalbi-ata/aiops/actions/runs/12345"
        ))
        # Syntax acceptance is never an assertion that this URL exists or proves FS147.

    def test_missing_stage(self):
        r = synthetic_receipt()
        del r["stages"]["worker_critic"]
        self.assertIn("missing stage worker_critic", gate.validate(r))

    def test_mixed_run(self):
        r = synthetic_receipt()
        r["stages"]["policy"]["run_id"] = "OTHER-RUN"
        self.assertIn("run mismatch policy", gate.validate(r))

    def test_wrong_glpi_ticket(self):
        r = synthetic_receipt()
        r["glpi_ticket_id"] = 146
        self.assertIn("ticket must be integer 147", gate.validate(r))

    def test_wrong_hitl_ticket(self):
        r = synthetic_receipt()
        r["stages"]["hitl_native"]["ticket_id"] = 146
        self.assertIn("HITL ticket mismatch", gate.validate(r))

    def test_cross_alert_hitl_rejected(self):
        r = synthetic_receipt()
        r["stages"]["hitl_native"]["alert_fingerprint"] = "OTHER-ALERT"
        self.assertIn("HITL alert fingerprint mismatch", gate.validate(r))

    def test_missing_hitl_alert_binding_rejected(self):
        r = synthetic_receipt()
        del r["stages"]["hitl_native"]["alert_fingerprint"]
        self.assertIn("HITL missing alert_fingerprint", gate.validate(r))

    def test_safe_resume_without_approval_binding_rejected(self):
        r = synthetic_receipt()
        del r["stages"]["safe_resume"]["approval_id"]
        self.assertIn("safe resume missing approval_id", gate.validate(r))

    def test_safe_resume_approval_from_other_run_rejected(self):
        r = synthetic_receipt()
        r["stages"]["safe_resume"]["approval_id"] = "OTHER-APPROVAL"
        self.assertIn("safe resume approval mismatch", gate.validate(r))

    def test_missing_native_action(self):
        r = synthetic_receipt()
        r["stages"]["hitl_native"]["action"] = ""
        self.assertIn("HITL missing action", gate.validate(r))

    def test_unverified_stage(self):
        r = synthetic_receipt()
        r["stages"]["prometheus"]["status"] = "UNKNOWN"
        self.assertIn("unverified stage prometheus", gate.validate(r))

    def test_live_mode_refused(self):
        r = synthetic_receipt()
        r["mode"] = "LIVE"
        self.assertIn("only DEMO lab evidence allowed", gate.validate(r))

    def test_production_claim_refused(self):
        r = synthetic_receipt()
        r["production_deployment"] = True
        self.assertIn("production deployment cannot be certified by lab gate", gate.validate(r))

    def test_resolved_without_post_measurement(self):
        r = synthetic_receipt()
        r["result"] = "RESOLVED"
        self.assertIn("RESOLVED without reviewable post-action proof URL", gate.validate(r))


    def test_resolved_with_placeholder_post_measurement_rejected(self):
        for url in ("https://example.invalid/fake", "http://evidence.invalid/post",
                    "https://localhost/post", "https://user:secret@evidence.example.org/post"):
            with self.subTest(url=url):
                r = synthetic_receipt()
                r["result"] = "RESOLVED"
                r["post_action_measurement_proof_url"] = url
                self.assertIn("RESOLVED without reviewable post-action proof URL", gate.validate(r))


if __name__ == "__main__":
    unittest.main()
