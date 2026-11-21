"""Synthetic, offline tests for the structural OCI BOM gate only."""
import copy
import unittest

from oci_release_gate import ROLES, validate


def synthetic_manifest():
    # Intentionally fictional: passing this gate is NOT release authorization.
    return {
        "schema_version": 1,
        "images": [
            {
                "role": role,
                "image": "registry.invalid/v3/" + role + "@sha256:" + "a" * 64,
                "source_commit": "b" * 40,
                "source_path": "https://github.com/invalid/source/tree/" + "b" * 40,
                "license_spdx": "MIT",
                "platforms": ["linux/amd64"],
                "sbom_sha256": "c" * 64,
                "provenance_sha256": "d" * 64,
                "signature_sha256": "e" * 64,
                "vulnerability_report_sha256": "f" * 64,
                "ci_run_url": "https://github.com/invalid/source/actions/runs/123",
                "ci_job_url": "https://github.com/invalid/source/actions/jobs/456",
                "verified_utc": "2026-11-21T18:00:00Z",
            }
            for role in sorted(ROLES)
        ],
    }


class OCIReleaseStructureTests(unittest.TestCase):
    def test_synthetic_manifest_passes_structure_only(self):
        self.assertTrue(validate(synthetic_manifest()))

    def test_missing_and_duplicate_role_denied(self):
        for mutation in ("missing", "duplicate"):
            with self.subTest(mutation=mutation):
                doc = synthetic_manifest()
                if mutation == "missing":
                    doc["images"].pop()
                else:
                    doc["images"][0]["role"] = doc["images"][1]["role"]
                with self.assertRaises(ValueError):
                    validate(doc)

    def test_mutable_or_fixture_image_denied(self):
        for value in ("registry.invalid/v3/core:latest", "fixture/core@sha256:" + "a" * 64):
            with self.subTest(value=value):
                doc = synthetic_manifest()
                doc["images"][0]["image"] = value
                with self.assertRaises(ValueError):
                    validate(doc)

    def test_missing_evidence_and_unknown_license_denied(self):
        for field, value in (("sbom_sha256", ""), ("license_spdx", "UNKNOWN"),
                             ("ci_job_url", "https://example.invalid/job/123"),
                             ("verified_utc", "2026-13-21T18:00:00Z")):
            with self.subTest(field=field):
                doc = synthetic_manifest()
                doc["images"][0][field] = value
                with self.assertRaises(ValueError):
                    validate(doc)

    def test_forged_but_well_formed_evidence_is_not_verified(self):
        doc = synthetic_manifest()
        self.assertTrue(validate(copy.deepcopy(doc)))
        # This is an explicit LIMITATION test: no network, SPDX registry,
        # image existence, signatures, or run/job relationship is checked.
        self.assertIn("registry.invalid", doc["images"][0]["image"])


if __name__ == "__main__":
    unittest.main()
