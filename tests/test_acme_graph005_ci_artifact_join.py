"""Pure in-memory ACME CI cross-artifact contract, never a runtime authority test."""
import copy
import hashlib
import json
import unittest
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory

from tools import acme_graph005_ci_artifact_join as join


class AcmeGraph005CIArtifactJoinTests(unittest.TestCase):
    HEAD = "1fd6391f8a8e7129246ec1b9e4a0d6d4c4eed688"

    def setUp(self):
        self.core = {
            "schema": "aiops.core-graph005-seven-015-source-receipt.v1",
            "source_head": self.HEAD, "graph_version": join.GRAPH,
            "source_fixture_only": True, "same_run_readback": "PASS_SYNTHETIC_ONLY",
            "transport": "DISPOSABLE_TLS_BASIC_BOUND", "portable_signature": "NONE",
            "decision": "UNKNOWN", "link_status": "UNKNOWN",
            "human_glpi_attested": False, "acme_full_event_equivalence": "NOT_VERIFIED",
            "hash_domains": dict(join.DOMAINS),
            "source_payload_sequence_domain": "PINNED_SOURCE_ORDINAL",
            "source_run_sequence_domain": "PHYSICAL_RUN_SEQUENCE",
            "source_payload_ordinals": list(range(1, 8)),
            "source_run_sequences": list(join.PHYSICAL), "same_run_source_count": 7,
            "events": [{"source_event_id": sid, "pinned_source_ordinal": i + 1,
                        "physical_run_sequence": join.PHYSICAL[i],
                        "core_pg16_full_event_sha256": hashlib.sha256(f"full-{i}".encode()).hexdigest(),
                        "core_pg16_payload_sha256": hashlib.sha256(f"payload-{i}".encode()).hexdigest()}
                       for i, sid in enumerate(join.SOURCE_IDS)],
        }
        self.worker = {
            "schema": "aiops.worker-graph005-two-os-negative.v1",
            "source_head": self.HEAD, "source_ids": list(join.SOURCE_IDS),
            "source_ordinals": list(range(1, 8)),
            "source_physical_sequences": list(join.PHYSICAL),
            "worker_os_processes": 2, "distinct_pids": True, "pg_major": 16,
            "verification": "UNVERIFIED", "human_glpi_attested": False,
            "portable_signature": "NONE", "execution_allowed": False,
            "effect_allowed": False, "effect_receipts": 0, "approve_count": 0,
            "temporal_signal_count": 0, "core_terminal_014_exercised": False,
            "core_outbox_replay_exercised": False,
            "source_after_revocation": "UNKNOWN", "reopen": "RECOMMENDED_NOT_EXECUTED",
        }

    def test_positive_structural_shape_is_not_a_positive_authority(self):
        result = join.build_receipt(self.core, self.worker, self.HEAD)
        self.assertEqual(result["cross_artifact_concordance"], "CONSISTENT_UNTRUSTED")
        self.assertEqual(result["independent_core_worker_same_run"], "NOT_ATTESTED")
        self.assertEqual(result["independent_actor_tenant_incident_run"], "NOT_ATTESTED")
        self.assertEqual(result["core_014_terminal_worker_join"], "NOT_ATTESTED")
        self.assertEqual((result["stage_count"], result["verified_stage_count"],
                          result["not_executed_stage_count"]), (15, 0, 15))
        self.assertEqual((result["checkpoint_count"], result["verified_checkpoint_count"],
                          result["not_executed_checkpoint_count"]), (6, 0, 6))
        self.assertEqual(result["twin_impact"]["candidate_impacted_ci_count"], 10)
        self.assertEqual(result["physical_run_sequences"], [1, 2, 4, 5, 6, 8, 9])
        self.assertFalse(result["publishable_to_core_or_glpi"])
        self.assertFalse(result["live_effects_authorized"])
        self.assertEqual(result["release_stable"], "NO_GO")

    def test_negative_mutations_rejected(self):
        cases = join.negative_controls(self.core, self.worker, self.HEAD)
        self.assertEqual(len(cases), 9)
        self.assertTrue(all(x["verdict"] == "REJECTED" for x in cases))

    def test_cross_artifact_head_is_not_an_authenticated_run(self):
        forged = copy.deepcopy(self.worker)
        forged["source_head"] = "a" * 40
        result = join.build_receipt(self.core, forged, self.HEAD)
        self.assertEqual(result["cross_artifact_concordance"], "UNKNOWN")
        self.assertEqual(result["cross_artifact_reason"], "CROSS_ARTIFACT_EXACT_HEAD_MISMATCH")
        self.assertEqual(result["not_executed_stage_count"], 15)
        self.assertEqual(result["not_executed_checkpoint_count"], 6)
        self.assertIsNone(result["runtime_run_id"])

    def test_zip_sha256_sidecar_crc_and_duplicate_json_fail_closed(self):
        data = json.dumps(self.core, sort_keys=True).encode()
        digest = hashlib.sha256(data).hexdigest()
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "receipt.zip"
            with zipfile.ZipFile(path, "w") as z:
                z.writestr(join.CORE_FILE, data)
                z.writestr("core-graph005-seven-015.sha256", digest + "  " + join.CORE_FILE + "\n")
            parsed, meta = join.read_artifact(path, join.CORE_FILE)
            self.assertEqual(parsed["source_head"], self.HEAD)
            self.assertTrue(meta["sha256_sidecar_verified"])
            with zipfile.ZipFile(path, "w") as z:
                z.writestr(join.CORE_FILE, b'{"x":1,"x":2}')
                z.writestr("core-graph005-seven-015.sha256", "a" * 64 + "  " + join.CORE_FILE)
            with self.assertRaisesRegex(ValueError, "SHA256 sidecar mismatch"):
                join.read_artifact(path, join.CORE_FILE)
            bad = b'{"x":1,"x":2}'
            with zipfile.ZipFile(path, "w") as z:
                z.writestr(join.CORE_FILE, bad)
                z.writestr("core-graph005-seven-015.sha256", hashlib.sha256(bad).hexdigest() + "  " + join.CORE_FILE)
            with self.assertRaisesRegex(ValueError, "duplicate JSON key"):
                join.read_artifact(path, join.CORE_FILE)


if __name__ == "__main__":
    unittest.main()
