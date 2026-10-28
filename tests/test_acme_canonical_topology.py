"""Offline ACME dual-fabric topology contract tests; no runtime/GLPI evidence."""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from fastapi import FastAPI
from fastapi.testclient import TestClient
from portal.acme_fixture_contract import (
    CANONICAL_DUAL_FABRIC_TOPOLOGY, load_fixture_bytes, validate_fixture,
)
from portal.acme_impact_read_model import FIXTURE_PATH, router


class CanonicalDualFabricTests(unittest.TestCase):
    def setUp(self):
        self.fixture = load_fixture_bytes(FIXTURE_PATH.read_bytes())

    def ci(self, data, ident):
        return next(ci for ci in data["ci"] if ci["id"] == ident)

    def test_declared_topology_and_simulation_remain_stable(self):
        report = validate_fixture(self.fixture)
        self.assertEqual(report["impact_path"],
                         ["SAN-FABRIC-A", "HOST-ESX-01", "VM-PAY-01", "APP-PAY-01"])
        self.assertEqual(len(CANONICAL_DUAL_FABRIC_TOPOLOGY), 6)
        self.assertEqual(report["provenance"], "SIMULATED_TARGET")
        self.assertFalse(report["live_remediation_authorized"])
        reordered = copy.deepcopy(self.fixture)
        self.ci(reordered, "HOST-ESX-01")["depends_on"].reverse()
        self.assertEqual(validate_fixture(reordered)["impact_path"], report["impact_path"])

    def test_rejects_shortcut_that_bypasses_host_and_vm(self):
        changed = copy.deepcopy(self.fixture)
        self.ci(changed, "APP-PAY-01")["depends_on"] = ["SAN-FABRIC-A"]
        with self.assertRaisesRegex(ValueError, "canonical ACME dual-fabric"):
            validate_fixture(changed)

    def test_rejects_missing_host_dependency_even_with_volume_path(self):
        changed = copy.deepcopy(self.fixture)
        self.ci(changed, "VM-PAY-01")["depends_on"] = ["VOL-PAY-01"]
        with self.assertRaisesRegex(ValueError, "canonical ACME dual-fabric"):
            validate_fixture(changed)

    def test_rejects_lost_redundant_fabric_even_when_a_path_exists(self):
        for ident in ("HOST-ESX-01", "VOL-PAY-01"):
            changed = copy.deepcopy(self.fixture)
            self.ci(changed, ident)["depends_on"] = ["SAN-FABRIC-A"]
            with self.subTest(ci=ident), self.assertRaisesRegex(
                    ValueError, "canonical ACME dual-fabric"):
                validate_fixture(changed)

    def test_rejects_kind_spoofing_and_missing_canonical_ci(self):
        changed = copy.deepcopy(self.fixture)
        self.ci(changed, "HOST-ESX-01")["kind"] = "Application"
        with self.assertRaisesRegex(ValueError, "canonical ACME dual-fabric"):
            validate_fixture(changed)
        missing = copy.deepcopy(self.fixture)
        missing["ci"] = [ci for ci in missing["ci"] if ci["id"] != "HOST-ESX-01"]
        missing["ci"].append({
            "id": "HOST-FAKE-01", "kind": "Host", "name": "fake", "depends_on": []
        })
        self.ci(missing, "VM-PAY-01")["depends_on"] = ["VOL-PAY-01"]
        with self.assertRaisesRegex(ValueError, "canonical ACME dual-fabric"):
            validate_fixture(missing)

    def test_invalid_topology_returns_503_not_a_demo_attestation(self):
        changed = copy.deepcopy(self.fixture)
        self.ci(changed, "HOST-ESX-01")["depends_on"] = ["SAN-FABRIC-A"]
        app = FastAPI()
        app.include_router(router)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "fixture.json"
            path.write_text(json.dumps(changed), encoding="utf-8")
            with patch("portal.acme_impact_read_model.FIXTURE_PATH", path):
                response = TestClient(app).get("/api/demo/acme-impact")
                self.assertEqual(response.status_code, 503)
                self.assertEqual(response.json()["detail"],
                                 "synthetic_impact_fixture_unavailable_or_invalid")
                self.assertNotIn("SIM-ACME-", response.text)


if __name__ == "__main__":
    unittest.main()
