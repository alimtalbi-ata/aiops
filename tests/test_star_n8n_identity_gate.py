"""Synthetic-only, no-network tests for the V1 02/03 identity handoff."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from demo.star_n8n_identity_gate import (
    FIELDS, STAGES, IdentityRejected, main, read_observations, verify_handoff,
)

IDENTITY = {"run_id": "RUN-ACME-001", "incident_id": "INC-ACME-001", "correlation_id": "CORR-ACME-001"}


def sample():
    return {stage: dict(IDENTITY) for stage in STAGES}


class N8nIdentityGateTests(unittest.TestCase):
    def test_consistent_and_not_a_business_attestation(self):
        report = verify_handoff(sample())
        self.assertEqual(report["result"], "CONSISTENT_UNAUTHENTICATED")
        self.assertEqual(len(report["identity_sha256"]), 64)
        for flag in ("runtime_execution_authenticated", "analyst_completed", "business_outcome_verified", "live_remediation_authorized"):
            self.assertFalse(report[flag])

    def test_deterministic_replay(self):
        self.assertEqual(verify_handoff(sample()), verify_handoff(copy.deepcopy(sample())))

    def test_missing_stage_fails_closed(self):
        for stage in STAGES:
            with self.subTest(stage=stage), self.assertRaises(IdentityRejected):
                payload = sample()
                del payload[stage]
                verify_handoff(payload)

    def test_missing_or_contradictory_identity_fails_at_every_stage(self):
        for stage in STAGES:
            for field in FIELDS:
                for replacement in (None, "OTHER-ACME-001"):
                    with self.subTest(stage=stage, field=field, replacement=replacement), self.assertRaises(IdentityRejected):
                        payload = sample()
                        payload[stage][field] = replacement
                        verify_handoff(payload)

    def test_refuses_traversal_and_fabricated_defaults(self):
        for invalid in ("", "x", "../../secret", "RUN X", 12, True, "X" * 97):
            with self.subTest(invalid=invalid), self.assertRaises(IdentityRejected):
                payload = sample()
                payload["prepare_analyst_03"]["run_id"] = invalid
                verify_handoff(payload)

    def test_identity_alias_or_shadow_field_rejected_at_every_stage(self):
        for stage in STAGES:
            for shadow in ({"runId": "RUN-OTHER-999"},
                           {"identity": {"run_id": "RUN-OTHER-999"}},
                           {"run_id_shadow": "RUN-OTHER-999"}):
                with self.subTest(stage=stage, shadow=shadow), self.assertRaisesRegex(
                        IdentityRejected, "identity schema mismatch"):
                    payload = sample()
                    payload[stage].update(shadow)
                    verify_handoff(payload)

    def test_extra_stage_rejected(self):
        with self.assertRaises(IdentityRejected):
            verify_handoff({**sample(), "post_hoc_recovery": dict(IDENTITY)})

    def test_duplicate_json_key_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "stages.json"
            path.write_text('{"webhook_02":{},"webhook_02":{}}')
            with self.assertRaises(IdentityRejected):
                read_observations(path)

    def test_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "stages.json"
            path.write_text(json.dumps(sample()))
            link = Path(td) / "alias.json"
            link.symlink_to(path)
            with self.assertRaises(IdentityRejected):
                read_observations(link)

    def test_cli_never_prints_untrusted_content(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "stages.json"
            path.write_text(json.dumps(sample()))
            self.assertEqual(main([str(path)]), 0)
            path.write_text(json.dumps({**sample(), "prepare_analyst_03": {"run_id": "DO_NOT_LEAK"}}))
            self.assertEqual(main([str(path)]), 2)


if __name__ == "__main__":
    unittest.main()
