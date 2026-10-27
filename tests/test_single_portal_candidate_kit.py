"""Isolated candidate-kit tests: no Docker, network, production, or real evidence."""
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from deploy import single_portal_candidate_kit as kit

COMMIT = "a" * 40


class CandidateKitTests(unittest.TestCase):
    def fixture(self, root):
        names = sorted(kit.APPROVED)
        for name in names:
            file = root / name
            file.parent.mkdir(parents=True, exist_ok=True)
            if name == "app/portal/platform_registry.py":
                components = tuple((f"svc-{n}", f"Service {n}", f"/service/{n}", "engine")
                                   for n in range(20))
                file.write_text("COMPONENTS=" + repr(components) + "\n", encoding="utf-8")
            else:
                file.write_text("# synthetic source fixture\n", encoding="utf-8")
        return names

    def test_only_explicit_root_level_sources_are_admitted(self):
        self.assertTrue(kit.safe_path("compose.yml"))
        self.assertFalse(kit.safe_path("unreviewed.yaml"))
        self.assertFalse(kit.safe_path("./compose.yml"))
        self.assertFalse(kit.safe_path("../compose.yml"))
        self.assertFalse(kit.safe_path("/compose.yml"))
        self.assertFalse(kit.safe_path("config/.env.demo.example"))

    def test_deterministic_cumulative_candidate_and_route_denial(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            root.mkdir()
            names = self.fixture(root)
            required_portal_sources = {
                "app/portal/main.py",
                "app/portal/acme-fixtures.json",
                "app/portal/acme_fixture_contract.py",
                "app/portal/acme_impact_read_model.py",
                ".github/workflows/acme-v21315-fixture-validation.yml",
                "demo/integrations/v21315/README.md",
                "demo/integrations/v21315/acme-fixtures.json",
                "demo/integrations/v21315/validate_fixture.py",
                "docs/demo/AIOPS-V21315-FIXTURE-GRAPH-VALIDATION-20261026.md",
                "docs/demo/AIOPS-V21315-PORTAL-IMPACT-READ-MODEL-20261026.md",
                "tests/test_acme_fixture_validation.py",
                "tests/test_portal_acme_impact_read_model.py",
                "tests/test_portal_bootstrap_read_model.py",
                "tests/test_portal_host_port_contract.py",
                "app/portal/platform_registry.py",
                "app/portal/platform_registry_router.py",
                "app/portal/portal_demo_public_v21310.py",
                "app/portal/public_demo_assets/AIOPS-EXECUTIVE-THEATER-PUBLIC.html",
                "tests/test_portal_demo_public_v21310.py",
                "tests/test_platform_registry_portal_route.py",
                "docs/release/AIOPS-SINGLE-PORTAL-CANDIDATE-20261025.md",
                "docs/release/AIOPS-PORTAL-ROUTE-INVENTORY-20261025.md",
                "docs/release/AIOPS-DEVELOPMENT-STATUS-AND-BLOCKERS-20261027.md",
                "docs/release/AIOPS-CANDIDATE-CODE-REUSE-REGISTER-20261027.md",
                "docs/release/AIOPS-HISTORICAL-EVIDENCE-CANDIDATE-AUDIT-20261027.md",
                "docs/recovery/HISTORICAL-CODE-REGISTRY-20261023.md",
                "docs/recovery/OCTOBER-2026-ARCHIVE-CONTEXT-AND-REUSE.md",
                ".github/workflows/star-capture-evidence.yml",
                ".github/workflows/star-event-capture-alignment-offline.yml",
                ".github/workflows/star-event-source-binding-offline.yml",
                "demo/star_event_capture_alignment.py",
                "demo/star_event_source_binding.py",
                "tests/test_star_event_capture_alignment.py",
                "tests/test_star_event_source_binding.py",
                "docs/demo/STAR-EVENT-SOURCE-BINDING-FAIL-CLOSED-20261027.md",
                "demo/star_capture_evidence.py",
                "demo/star_png_integrity.py",
                "demo/star_snapshot_choreography.py",
                "docs/demo/AIOPS-STAR-EVIDENCE-MANIFEST-STRICTNESS-20261026.md",
                "tests/test_star_capture_evidence.py",
                "tests/test_star_png_integrity.py",
                "tests/test_star_snapshot_choreography.py",
                ".github/workflows/star-evidence-manifest.yml",
                "demo/star_evidence_manifest.py",
                "tests/test_star_evidence_manifest.py",
                "docs/demo/STAR-OFFLINE-EVIDENCE-MANIFEST-20261027.md",
            }
            self.assertTrue(required_portal_sources.issubset(set(kit.APPROVED)))
            self.assertTrue(kit.safe_path(
                "app/portal/public_demo_assets/AIOPS-EXECUTIVE-THEATER-PUBLIC.html"))
            with patch.object(kit, "source_paths", return_value=(COMMIT, names)):
                first = root.parent / "first.zip"
                second = root.parent / "second.zip"
                a = kit.build(root, first, COMMIT)
                b = kit.build(root, second, COMMIT)
            self.assertEqual(a["sha256"], b["sha256"])
            self.assertEqual(a["routes"], 20)
            self.assertFalse(a["production_qualified"])
            with zipfile.ZipFile(first) as z:
                manifest = json.loads(z.read("metadata/source-manifest.json"))
                routes = json.loads(z.read("metadata/planned-routes.json"))
                self.assertEqual(manifest["commit"], COMMIT)
                self.assertEqual(manifest["embedded_count"], len(kit.APPROVED))
                self.assertEqual(
                    z.read("sources/app/portal/public_demo_assets/AIOPS-EXECUTIVE-THEATER-PUBLIC.html"),
                    (root / "app/portal/public_demo_assets/AIOPS-EXECUTIVE-THEATER-PUBLIC.html").read_bytes(),
                )
                self.assertIn("sources/app/portal/main.py", z.namelist())
                self.assertIn("sources/app/portal/ui_theme.py", z.namelist())
                self.assertEqual(
                    z.read("sources/app/portal/ui_theme.py"),
                    (root / "app/portal/ui_theme.py").read_bytes(),
                )
                self.assertIn("sources/app/portal/portal_demo_public_v21310.py", z.namelist())
                self.assertIn("sources/tests/test_portal_demo_public_v21310.py", z.namelist())
                self.assertIn("sources/tests/test_portal_host_port_contract.py", z.namelist())
                self.assertIn("sources/docs/release/AIOPS-PORTAL-ROUTE-INVENTORY-20261025.md", z.namelist())
                for release_doc in (
                    "docs/release/AIOPS-DEVELOPMENT-STATUS-AND-BLOCKERS-20261027.md",
                    "docs/release/AIOPS-CANDIDATE-CODE-REUSE-REGISTER-20261027.md",
                    "docs/release/AIOPS-HISTORICAL-EVIDENCE-CANDIDATE-AUDIT-20261027.md",
                ):
                    member = "sources/" + release_doc
                    self.assertIn(member, z.namelist())
                    self.assertEqual(z.read(member), (root / release_doc).read_bytes())
                cumulative_acme_sources = {
                    ".github/workflows/acme-v21315-fixture-validation.yml",
                    "demo/integrations/v21315/README.md",
                    "demo/integrations/v21315/acme-fixtures.json",
                    "demo/integrations/v21315/validate_fixture.py",
                    "docs/demo/AIOPS-V21315-FIXTURE-GRAPH-VALIDATION-20261026.md",
                    "tests/test_acme_fixture_validation.py",
                    "app/portal/acme_impact_read_model.py",
                    "tests/test_portal_acme_impact_read_model.py",
                    "tests/test_portal_bootstrap_read_model.py",
                    "docs/demo/AIOPS-V21315-PORTAL-IMPACT-READ-MODEL-20261026.md",
                }
                for source_path in cumulative_acme_sources:
                    member = "sources/" + source_path
                    self.assertIn(member, z.namelist())
                    self.assertEqual(z.read(member), (root / source_path).read_bytes())
                cumulative_evidence_sources = {
                    ".github/workflows/star-capture-evidence.yml",
                    "demo/star_capture_evidence.py",
                    "demo/star_png_integrity.py",
                    "demo/star_snapshot_choreography.py",
                    "docs/demo/AIOPS-STAR-EVIDENCE-MANIFEST-STRICTNESS-20261026.md",
                    "tests/test_star_capture_evidence.py",
                    "tests/test_star_png_integrity.py",
                    "tests/test_star_snapshot_choreography.py",
                }
                for source_path in cumulative_evidence_sources:
                    member = "sources/" + source_path
                    self.assertIn(member, z.namelist())
                    self.assertEqual(z.read(member), (root / source_path).read_bytes())
                cumulative_time_alignment_sources = {
                    ".github/workflows/star-event-capture-alignment-offline.yml",
                    "demo/star_event_capture_alignment.py",
                    "tests/test_star_event_capture_alignment.py",
                }
                for source_path in cumulative_time_alignment_sources:
                    member = "sources/" + source_path
                    self.assertIn(member, z.namelist())
                    self.assertEqual(z.read(member), (root / source_path).read_bytes())
                cumulative_source_binding_sources = {
                    ".github/workflows/star-event-source-binding-offline.yml",
                    "demo/star_event_source_binding.py",
                    "tests/test_star_event_source_binding.py",
                    "docs/demo/STAR-EVENT-SOURCE-BINDING-FAIL-CLOSED-20261027.md",
                }
                for source_path in cumulative_source_binding_sources:
                    member = "sources/" + source_path
                    self.assertIn(member, z.namelist())
                    self.assertEqual(z.read(member), (root / source_path).read_bytes())
                cumulative_manifest_sources = {
                    ".github/workflows/star-evidence-manifest.yml",
                    "demo/star_evidence_manifest.py",
                    "tests/test_star_evidence_manifest.py",
                    "docs/demo/STAR-OFFLINE-EVIDENCE-MANIFEST-20261027.md",
                }
                for source_path in cumulative_manifest_sources:
                    member = "sources/" + source_path
                    self.assertIn(member, z.namelist())
                    self.assertEqual(z.read(member), (root / source_path).read_bytes())
                self.assertTrue(all(not row["route_mounted"] and
                                    not row["runtime_authenticated"]
                                    for row in routes["routes"]))
                self.assertIn("NO PRODUCTION DEPLOYMENT", z.read("metadata/README.md").decode())
                self.assertIn("metadata/planned-routes.json", z.read("metadata/SHA256SUMS").decode())

    def test_reject_duplicate_planned_path_with_distinct_component_ids(self):
        components = [(f"svc-{n}", f"Service {n}", f"/service/{n}", "engine")
                      for n in range(20)]
        components[1] = ("svc-1", "Service 1", "/service/0", "engine")
        with self.assertRaisesRegex(ValueError, "unsafe or duplicate planned route"):
            kit.registry_routes(("COMPONENTS=" + repr(tuple(components))).encode())

    def test_reject_unsafe_route_aliases_and_invalid_registry_metadata(self):
        components = [(f"svc-{n}", f"Service {n}", f"/service/{n}", "engine")
                      for n in range(20)]
        invalid_rows = [
            ("svc-0", "Service 0", "/service/../admin", "engine"),
            ("svc-0", "Service 0", "/service/%2e%2e/admin", "engine"),
            ("svc-0", "Service 0", "/service//admin", "engine"),
            ("svc-0", "Service 0", "/service?mode=live", "engine"),
            ("svc-0", "Service 0", "/service#fragment", "engine"),
            ("svc-0", "Service 0", "/Service", "engine"),
            ("svc-0", "Service 0", "/service/0/", "engine"),
            ("svc-0", "Service 0", "/", "engine"),
            ("svc 0", "Service 0", "/service/0", "engine"),
            ("svc-0", "Service 0", "/service/0", "unrecognized"),
            ("svc-0", "Service\n0", "/service/0", "engine"),
        ]
        for row in invalid_rows:
            with self.subTest(row=row):
                components[0] = row
                with self.assertRaisesRegex(ValueError, "unsafe or duplicate planned route"):
                    kit.registry_routes(("COMPONENTS=" + repr(tuple(components))).encode())

    def test_reject_missing_approved_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            root.mkdir()
            names = self.fixture(root)
            names.remove(kit.APPROVED[0])
            with patch.object(kit, "source_paths", return_value=(COMMIT, names)):
                with self.assertRaisesRegex(ValueError, "approved source missing"):
                    kit.build(root, root.parent / "missing.zip", COMMIT)

    def test_reject_secret_and_leave_no_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            root.mkdir()
            names = self.fixture(root)
            (root / kit.APPROVED[0]).write_bytes(b"-----BEGIN PRIVATE KEY-----\nsecret")
            output = root.parent / "sensitive.zip"
            with patch.object(kit, "source_paths", return_value=(COMMIT, names)):
                with self.assertRaisesRegex(ValueError, "sensitive"):
                    kit.build(root, output, COMMIT)
            self.assertFalse(output.exists())

    def test_reject_wrong_pin_and_existing_zip(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            root.mkdir()
            names = self.fixture(root)
            output = root.parent / "existing.zip"
            output.write_bytes(b"do-not-overwrite")
            with patch.object(kit, "source_paths", return_value=(COMMIT, names)):
                with self.assertRaisesRegex(ValueError, "already exists"):
                    kit.build(root, output, COMMIT)
                with self.assertRaisesRegex(ValueError, "pinned commit mismatch"):
                    kit.build(root, root.parent / "new.zip", "b" * 40)
            self.assertEqual(output.read_bytes(), b"do-not-overwrite")

    def test_reject_symlink_and_unsafe_path(self):
        self.assertFalse(kit.safe_path("docs/../secrets/key.py"))
        self.assertFalse(kit.safe_path("reports/capture.png"))
        self.assertFalse(kit.safe_path("docs/.env.production"))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            root.mkdir()
            names = self.fixture(root)
            path = root / kit.APPROVED[0]
            path.unlink()
            path.symlink_to(root / kit.APPROVED[1])
            with patch.object(kit, "source_paths", return_value=(COMMIT, names)):
                with self.assertRaisesRegex(ValueError, "unsafe tracked source"):
                    kit.build(root, root.parent / "symlink.zip", COMMIT)


if __name__ == "__main__":
    unittest.main()
