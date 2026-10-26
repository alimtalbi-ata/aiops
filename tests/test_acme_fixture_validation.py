"""Offline contract tests for the ACME synthetic dependency/impact fixture."""
from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from demo.integrations.v21315.validate_fixture import load_fixture, validate_fixture

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = ROOT / "demo" / "integrations" / "v21315" / "acme-fixtures.json"
VALIDATOR_PATH = FIXTURE_PATH.with_name("validate_fixture.py")
BASE_FIXTURE = load_fixture(FIXTURE_PATH)


class AcmeFixtureValidationTests(unittest.TestCase):
    def fixture(self):
        return copy.deepcopy(BASE_FIXTURE)

    def test_san_p1_has_deterministic_transitive_payments_p2_impact(self):
        report = validate_fixture(self.fixture())
        self.assertEqual(report["source_incident_id"], "ACME-DEMO-SAN-001")
        self.assertEqual(report["target_incident_id"], "ACME-DEMO-PAY-002")
        self.assertEqual(
            report["impact_path"],
            ["SAN-FABRIC-A", "HOST-ESX-01", "VM-PAY-01", "APP-PAY-01"],
        )
        self.assertEqual(report["provenance"], "SIMULATED_TARGET")
        self.assertFalse(report["live_remediation_authorized"])

    def test_rejects_unknown_ci_dependency(self):
        data = self.fixture()
        data["ci"][0]["depends_on"] = ["CI-DOES-NOT-EXIST"]
        with self.assertRaisesRegex(ValueError, "unknown CI dependency"):
            validate_fixture(data)

    def test_rejects_dependency_cycle(self):
        data = self.fixture()
        by_id = {item["id"]: item for item in data["ci"]}
        by_id["VM-PAY-01"]["depends_on"].append("APP-PAY-01")
        with self.assertRaisesRegex(ValueError, "dependency cycle"):
            validate_fixture(data)

    def test_rejects_missing_transitive_san_to_payments_path(self):
        data = self.fixture()
        for item in data["ci"]:
            item["depends_on"] = [
                dependency for dependency in item["depends_on"]
                if dependency != "SAN-FABRIC-A"
            ]
        with self.assertRaisesRegex(ValueError, "transitive dependency path"):
            validate_fixture(data)

    def test_rejects_duplicate_ci_ids(self):
        data = self.fixture()
        data["ci"][1]["id"] = data["ci"][0]["id"]
        with self.assertRaisesRegex(ValueError, "duplicate CI id"):
            validate_fixture(data)

    def test_rejects_duplicate_dependency_reference(self):
        data = self.fixture()
        data["ci"][0]["depends_on"].append(data["ci"][0]["depends_on"][0])
        with self.assertRaisesRegex(ValueError, "duplicate references"):
            validate_fixture(data)

    def test_rejects_non_simulated_provenance(self):
        data = self.fixture()
        data["provenance"] = "OBSERVED_RUNTIME"
        with self.assertRaisesRegex(ValueError, "SIMULATED_TARGET"):
            validate_fixture(data)

    def test_rejects_live_remediation_and_unknown_actions(self):
        data = self.fixture()
        data["incidents"][0]["live_remediation"] = True
        with self.assertRaisesRegex(ValueError, "deny live remediation"):
            validate_fixture(data)

        data = self.fixture()
        data["incidents"][0]["allowed_actions"].append("execute")
        with self.assertRaisesRegex(ValueError, "outside the simulation allowlist"):
            validate_fixture(data)

    def test_rejects_duplicate_json_object_keys(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "duplicate.json"
            path.write_text('{"schema":"first","schema":"second"}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "duplicate JSON object key"):
                load_fixture(path)

    def test_invalid_impact_fails_closed_under_optimized_python(self):
        data = self.fixture()
        for item in data["ci"]:
            item["depends_on"] = [
                dependency for dependency in item["depends_on"]
                if dependency != "SAN-FABRIC-A"
            ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid-acme-fixture.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            completed = subprocess.run(
                [sys.executable, "-O", str(VALIDATOR_PATH), str(path)],
                cwd=ROOT,
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
        self.assertEqual(completed.returncode, 2)
        self.assertIn("AIOPS_DEMO_FIXTURES=FAIL", completed.stderr)
        self.assertIn("transitive dependency path", completed.stderr)


if __name__ == "__main__":
    unittest.main()
