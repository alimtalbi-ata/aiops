import datetime as dt
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "acme"


def load(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_SNAPSHOT = ROOT / "docs/contracts/acme-receipt.schema.json"
P = ROOT / "scripts/acme_demo_readiness.py"
spec = importlib.util.spec_from_file_location("acme_demo_readiness", P)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
NOW = dt.datetime(2026, 11, 16, 17, 0, tzinfo=dt.timezone.utc)


class Readiness(unittest.TestCase):
    def test_pass_is_simulation_only(self):
        result = m.assess(load("valid.json"), NOW)
        self.assertEqual(result["verdict"], "GO_SIMULATION_ONLY")
        self.assertEqual(result["live"], "NO_GO")

    def test_wrong_terminal_reason(self):
        self.assertEqual(m.assess(load("wrong_reason.json"), NOW)["verdict"], "NO_GO")

    def test_real_ticket_identifier_refused(self):
        self.assertEqual(m.assess(load("real_ticket.json"), NOW)["verdict"], "NO_GO")

    def test_non_simulated_approval_identifier_refused(self):
        self.assertEqual(m.assess(load("real_approval.json"), NOW)["verdict"], "NO_GO")

    def test_missing_attempt_identifier(self):
        self.assertEqual(m.assess(load("missing_attempt_id.json"), NOW)["verdict"], "NO_GO")

    def test_malformed_attempt_identifier(self):
        self.assertEqual(m.assess(load("malformed_attempt_id.json"), NOW)["verdict"], "NO_GO")

    def test_missing_receipt(self):
        self.assertEqual(m.assess(None, NOW)["verdict"], "NO_GO")

    def test_no_live_claim(self):
        self.assertEqual(m.assess(load("live_effects.json"), NOW)["verdict"], "NO_GO")

    def test_no_real_glpi(self):
        self.assertEqual(m.assess(load("real_glpi.json"), NOW)["verdict"], "NO_GO")

    def test_no_fake_human(self):
        self.assertEqual(m.assess(load("fake_human.json"), NOW)["verdict"], "NO_GO")

    def test_no_host_mutation(self):
        self.assertEqual(m.assess(load("docker_mutation.json"), NOW)["verdict"], "NO_GO")

    def test_missing_twin_capability_blocks(self):
        self.assertEqual(m.assess(load("missing_twin.json"), NOW)["verdict"], "NO_GO")

    def test_failed_worker_receipt_blocks(self):
        self.assertEqual(m.assess(load("failed_worker.json"), NOW)["verdict"], "NO_GO")

    def test_missing_stage(self):
        self.assertEqual(m.assess(load("empty_stages.json"), NOW)["verdict"], "NO_GO")

    def test_missing_id(self):
        self.assertEqual(m.assess(load("missing_ticket_id.json"), NOW)["verdict"], "NO_GO")

    def test_stale(self):
        self.assertEqual(m.assess(load("stale.json"), NOW)["verdict"], "NO_GO")

    def test_future(self):
        self.assertEqual(m.assess(load("future.json"), NOW)["verdict"], "NO_GO")

    def test_no_pass_on_boolean_zero(self):
        self.assertEqual(m.assess(load("boolean_zero.json"), NOW)["verdict"], "NO_GO")

    def test_unknown_receipt_field_is_rejected(self):
        r = load("valid.json")
        r["unexpected_runtime_claim"] = "PASS"
        self.assertEqual(m.assess(r, NOW)["verdict"], "NO_GO")

    def test_unknown_identifier_field_is_rejected(self):
        r = load("valid.json")
        r["ids"]["unexpected"] = "OTHER"
        self.assertEqual(m.assess(r, NOW)["verdict"], "NO_GO")

    def test_whitespace_only_identifier_is_rejected(self):
        r = load("valid.json")
        r["ids"]["run_id"] = "  "
        self.assertEqual(m.assess(r, NOW)["verdict"], "NO_GO")

    def test_timestamp_must_include_timezone(self):
        r = load("valid.json")
        r["collected_at"] = "2026-11-16T16:55:00"
        self.assertEqual(m.assess(r, NOW)["verdict"], "NO_GO")


class Hardening(unittest.TestCase):
    def test_mutations(self):
        for key, value in (("human_approval_claimed", 0), ("live_effects_allowed", 0.0),
                           ("real_glpi_writes_allowed", 0), ("collected_at", "2026-11-16T17:55:00+01:00"),
                           ("collected_at", "1794848100")):
            with self.subTest(key=key, value=value):
                r = load("valid.json")
                r[key] = value
                self.assertEqual(m.assess(r, NOW)["verdict"], "NO_GO")
        for key, value in (("ticket_id", "SIM-GLPI-"), ("approval_id", "SIM-APP- "),
                           ("approval_id", "SIM-APP-")):
            with self.subTest(key=key):
                r = load("valid.json")
                r["ids"][key] = value
                self.assertEqual(m.assess(r, NOW)["verdict"], "NO_GO")
        r = load("valid.json")
        r["stages"]["unknown_stage"] = "PASS"
        self.assertEqual(m.assess(r, NOW)["verdict"], "NO_GO")

    def test_duplicate_keys(self):
        with self.assertRaises(ValueError):
            json.loads('{"status":"BLOCKED","status":"PASS"}', object_pairs_hook=m._unique_object)
        with self.assertRaises(ValueError):
            json.loads('{"ids":{"run_id":"A","run_id":"B"}}', object_pairs_hook=m._unique_object)


class DirectReceiptModel(unittest.TestCase):
    """Check the strict model directly, independent of assess() formatting."""

    def test_valid_model(self):
        value = m.AcmeReceipt.model_validate_json(
            json.dumps(load("valid.json")), context={"now": NOW}
        )
        self.assertEqual(value.mode, "SIMULATION")
        self.assertEqual(value.docker_mutations, 0)

    def test_invalid_attempt_ids(self):
        for attempt in ("ACME-SIM-FAKE", "ACME-SIM-0123456789abcdef", "", "RANDOM"):
            with self.subTest(attempt_id=attempt):
                value = load("valid.json")
                value["attempt_id"] = attempt
                with self.assertRaises(m.ValidationError):
                    m.AcmeReceipt.model_validate_json(
                        json.dumps(value), context={"now": NOW}
                    )

    def test_security_flags_and_types(self):
        for key, invalid in (
            ("mode", "LIVE"), ("live_effects_allowed", True),
            ("human_approval_claimed", True), ("real_glpi_writes_allowed", True),
            ("docker_mutations", False), ("docker_mutations", "0"),
        ):
            with self.subTest(field=key, value=invalid):
                value = load("valid.json")
                value[key] = invalid
                with self.assertRaises(m.ValidationError):
                    m.AcmeReceipt.model_validate_json(
                        json.dumps(value), context={"now": NOW}
                    )

    def test_direct_model_negative_fixtures(self):
        for path in sorted(FIXTURES.glob("*.json")):
            if path.name == "valid.json":
                continue
            with self.subTest(fixture=path.name):
                with self.assertRaises(m.ValidationError):
                    m.AcmeReceipt.model_validate_json(
                        path.read_text(encoding="utf-8"),
                        context={"now": NOW},
                    )

    def test_all_negative_fixtures_via_assess(self):
        expected = {
            "wrong_reason", "real_ticket", "real_approval",
            "missing_attempt_id", "malformed_attempt_id", "live_effects",
            "real_glpi", "fake_human", "docker_mutation", "boolean_zero",
            "missing_twin", "failed_worker", "empty_stages",
            "missing_ticket_id", "stale", "future",
        }
        found = {path.stem for path in FIXTURES.glob("*.json")}
        self.assertEqual(found, expected | {"valid"})
        for name in sorted(expected):
            with self.subTest(fixture=name):
                self.assertEqual(m.assess(load(name + ".json"), NOW)["verdict"], "NO_GO")


class JsonSchemaSnapshot(unittest.TestCase):
    """Fail if the committed schema is absent or diverges from the model."""

    def schema(self):
        return m.AcmeReceipt.model_json_schema(mode="validation")

    def test_schema_required_fields(self):
        schema = self.schema()
        self.assertEqual(schema["type"], "object")
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(set(schema["required"]), {
            "schema", "collected_at", "attempt_id", "tenant_id",
            "scenario_id", "mode", "status", "reason", "approval_issuer",
            "human_approval_claimed", "live_effects_allowed",
            "real_glpi_writes_allowed", "docker_mutations", "stages", "ids",
        })

    def test_schema_security_constraints(self):
        props = self.schema()["properties"]
        self.assertEqual(props["mode"]["const"], "SIMULATION")
        self.assertIs(props["live_effects_allowed"]["const"], False)
        self.assertEqual(props["attempt_id"]["pattern"], "^ACME-SIM-[A-F0-9]{16}$")
        self.assertEqual(props["docker_mutations"]["minimum"], 0)
        self.assertEqual(props["docker_mutations"]["maximum"], 0)

    def test_snapshot_matches_committed_contract(self):
        self.assertTrue(SCHEMA_SNAPSHOT.is_file(), "Versioned schema snapshot is required")
        current = self.schema()
        committed = json.loads(SCHEMA_SNAPSHOT.read_text(encoding="utf-8"))
        canonical = lambda value: json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        )
        a, b = canonical(current), canonical(committed)
        if a != b:
            self.fail(
                "ACME schema snapshot mismatch; regenerate and review. "
                f"current={hashlib.sha256(a.encode()).hexdigest()[:12]} "
                f"committed={hashlib.sha256(b.encode()).hexdigest()[:12]}"
            )

    def test_schema_generation_deterministic(self):
        self.assertEqual(self.schema(), self.schema())

if __name__ == "__main__":
    unittest.main()
