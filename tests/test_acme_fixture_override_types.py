"""ACME pinned graph/catalog type-integrity regressions (offline, SYNTHETIC)."""
import copy
import unittest

from tools import generate_acme_incidents as gen


class AcmeFixtureOverrideTypesTests(unittest.TestCase):
    def test_python_numeric_aliases_cannot_override_pinned_graph(self):
        graph = gen.load_graph()
        for section, field in (("nodes", "criticality"), ("edges", "redundancy")):
            with self.subTest(section=section):
                altered = copy.deepcopy(graph)
                key = next(iter(altered[section]))
                altered[section][key][field] = float(altered[section][key][field])
                self.assertEqual(altered, graph)  # Python's permissive numeric equality
                with self.assertRaisesRegex(ValueError, "unpinned graph override"):
                    gen.replay(graph=altered)

    def test_catalog_numeric_alias_cannot_change_dedupe_bucket(self):
        catalog, _ = gen.load_catalog()
        altered = copy.deepcopy(catalog)
        scenario = next(s for s in altered["scenarios"]
                        if s["key"] == "REDUNDANT_SAN_PATH_LOSS")
        scenario["frequency_seconds"] = float(scenario["frequency_seconds"])
        self.assertEqual(altered, catalog)
        with self.assertRaisesRegex(ValueError, "unpinned catalog override"):
            gen.replay(catalog=altered)

    def test_unchanged_replay_is_still_pinned_and_unattested(self):
        baseline = gen.replay()
        self.assertEqual(baseline, gen.replay(graph=gen.load_graph(), catalog=gen.load_catalog()[0]))
        self.assertEqual(baseline["event_count"], 7)
        self.assertEqual(baseline["correlation_status"], "OFFLINE_SYNTHETIC_ONLY")
        self.assertIsNone(baseline["incident_id"])
        self.assertIsNone(baseline["run_id"])
        self.assertEqual(baseline["evidence_ids"], [])
        self.assertTrue(all(c["status"] == "NOT_EXECUTED" for c in baseline["checkpoints"]))



class AcmeCoreProducerSevenMappingTests(unittest.TestCase):
    """Negative-only Core #291 producer hash mapping, no runtime authority."""

    @classmethod
    def setUpClass(cls):
        import hashlib
        from tools import acme_synthetic_core_producer_mapping as mapping
        cls.mapping = mapping
        cls.manifest = gen.replay(seed=20261018)
        cls.fixture = mapping.build_fixture(cls.manifest)
        cls.now = 1793520000

    def proposal(self):
        m = self.mapping
        return {"schema": m.SCHEMA, "source": m.SOURCE,
                "test_partition": m.PARTITION, "tenant_id": m.TENANT,
                "actor_subject": m.ACTOR, "observed_at": self.now - 30,
                "known_at": self.now - 20, "expires_at": self.now + 60,
                "revoked": False, "verified": False, "core_receipt": None,
                "source_event_rows": copy.deepcopy(self.fixture["source_event_rows"])}

    def test_deterministic_pinned_seven_events(self):
        import re
        f = self.fixture
        self.assertEqual(f, self.mapping.build_fixture(gen.replay()))
        self.assertEqual(f["seed"], 20261018)
        self.assertEqual(f["graph_version"], gen.SEED_GIT_BLOB)
        self.assertEqual(f["source_replay_sha256"],
                         "bfe0f0f14fc6229d47e641c8d4c6b9ae1600dcbf729f5f0b988960a8e62a70b8")
        self.assertEqual([r["source_event_id"] for r in f["source_event_rows"]],
                         [e["source_event_id"] for e in self.manifest["events"]])
        for n, row in enumerate(f["source_event_rows"], 1):
            self.assertEqual(row["sequence"], n)
            self.assertEqual(len(set(row["sha256_domains"].values())), 3)
            self.assertTrue(all(re.fullmatch(r"[0-9a-f]{64}", h)
                                for h in row["sha256_domains"].values()))

    def test_core_291_schema_and_canonical_hash(self):
        import hashlib
        from tools import acme_synthetic_core_canonical_cross_domain as cross
        code = (gen.ROOT / "app/core/actor_canonical_seven_source.py").read_text()
        for name, value in (("SCHEMA", self.mapping.CORE_SOURCE),
                            ("RECEIPT_SCHEMA", self.mapping.CORE_RECEIPT),
                            ("PAYLOAD_DOMAIN", self.mapping.PAYLOAD),
                            ("FULL_DOMAIN", self.mapping.FULL),
                            ("RECEIPT_PROOF_DOMAIN", self.mapping.PROOF),
                            ("RECEIPT_HASH_DOMAIN", self.mapping.RECEIPT_HASH)):
            self.assertIn('%s = "%s"' % (name, value), code)
        for row, proposal in zip(self.fixture["source_event_rows"],
                                 cross.proposed_cross_domain_rows(self.manifest)):
            digest = hashlib.sha256(gen._canonical({
                "schema": self.mapping.PAYLOAD,
                "event": proposal["proposed_core_event"]})).hexdigest()
            self.assertEqual(digest, row["sha256_domains"]["proposed_core_payload"])

    def test_matching_proposal_never_verifies_core(self):
        for proposal in (None, self.proposal()):
            result = self.mapping.verify_fixture(self.manifest, proposal=proposal,
                                                 now=self.now)
            self.assertEqual(result["result"], "UNAVAILABLE")
            self.assertFalse(result["actor_authenticated"])
            self.assertFalse(result["tenant_acl_qualified"])
            self.assertIsNone(result["core_runtime_receipt"])
            self.assertIsNone(result["incident_id"])
            self.assertIsNone(result["run_id"])

    def test_fifteen_itil_stages_and_six_checkpoints_unexecuted(self):
        f = self.fixture
        self.assertEqual(len(f["itil_stages"]), 15)
        self.assertEqual(len(f["checkpoints"]), 6)
        self.assertTrue(all(x["status"] == "NOT_EXECUTED" for x in f["itil_stages"]))
        self.assertTrue(all(x["status"] == "NOT_EXECUTED" and x["id"] is None
                            for x in f["checkpoints"]))
        self.assertTrue(all(f["runtime_authority"][k] is None for k in
                            ("tenant_id", "actor_subject", "incident_id",
                             "run_id", "glpi_ticket_id", "hitl_approval")))

    def test_foreign_actor_tenant_and_partition_fail_closed(self):
        for key, value in (("actor_subject", "TEST_ONLY_ACTOR_B"),
                           ("tenant_id", "TEST_ONLY_TENANT_B"),
                           ("test_partition", "SYNTHETIC_TEST_PARTITION_B")):
            p = self.proposal()
            p[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.mapping.verify_fixture(self.manifest, proposal=p, now=self.now)

    def test_stale_future_expired_revoked_fail_closed(self):
        for key, value in (("observed_at", self.now - 301),
                           ("known_at", self.now + 1),
                           ("expires_at", self.now),
                           ("revoked", True)):
            p = self.proposal()
            p[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.mapping.verify_fixture(self.manifest, proposal=p, now=self.now)

    def test_fake_receipt_and_verified_authority_rejected(self):
        for key, value in (("verified", True),
                           ("source", "CORE_CANONICAL_READBACK"),
                           ("core_receipt", {"decision": "ALLOW"})):
            p = self.proposal()
            p[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.mapping.verify_fixture(self.manifest, proposal=p, now=self.now)

    def test_missing_duplicate_reordered_and_swapped_hashes_rejected(self):
        changes = (
            lambda p: p["source_event_rows"].pop(),
            lambda p: p["source_event_rows"].reverse(),
            lambda p: p["source_event_rows"].__setitem__(
                1, copy.deepcopy(p["source_event_rows"][0])),
            lambda p: p["source_event_rows"][0]["sha256_domains"].update(
                acme_full_event="0" * 64),
        )
        for change in changes:
            p = self.proposal()
            change(p)
            with self.assertRaises(ValueError):
                self.mapping.verify_fixture(self.manifest, proposal=p, now=self.now)

    def test_runtime_forgery_and_replay_tampering_rejected(self):
        for key, value in (("core_runtime_receipt", {"fake": True}),
                           ("core_hash_domain_equivalence", True),
                           ("runtime_readback", "EXECUTED")):
            f = copy.deepcopy(self.fixture)
            f[key] = value
            with self.assertRaises(ValueError):
                self.mapping.verify_fixture(self.manifest, fixture=f)
        for key, value in (("seed", 20261019), ("graph_version", "FAKE")):
            m = copy.deepcopy(self.manifest)
            m[key] = value
            with self.assertRaises(ValueError):
                self.mapping.build_fixture(m)
        m = copy.deepcopy(self.manifest)
        m["events"][0]["event_time"] = "2026-10-31T09:41:00Z"
        with self.assertRaises(ValueError):
            self.mapping.build_fixture(m)

    def test_cli_machine_readable_replay_is_byte_deterministic(self):
        import json
        import subprocess
        import sys
        cmd = [sys.executable, "-m", "tools.acme_synthetic_core_producer_mapping"]
        a = subprocess.run(cmd + ["--emit"], cwd=gen.ROOT,
                           capture_output=True, text=True)
        b = subprocess.run(cmd + ["--emit"], cwd=gen.ROOT,
                           capture_output=True, text=True)
        self.assertEqual(a.returncode, 0, a.stderr)
        self.assertEqual(a.stdout, b.stdout)
        self.assertEqual(json.loads(a.stdout), self.fixture)
        check = subprocess.run(cmd + ["--check"], cwd=gen.ROOT,
                               capture_output=True, text=True)
        self.assertEqual(check.returncode, 0, check.stderr)
        self.assertEqual(json.loads(check.stdout)["result"], "UNAVAILABLE")


if __name__ == "__main__":
    unittest.main()
