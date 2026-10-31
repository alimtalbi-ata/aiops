"""Offline release inventory guard regressions; no production or network access."""

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from check_cumulative_release_kit import audit_kit
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "deploy"))
from refresh_release_inventory import refresh


class CumulativeKitGateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / "source"
        self.source.mkdir()
        self.files = {"README.md": b"AIOps synthetic test\n", "db/migrations/011_hitl_decision_outbox.sql": b"-- test\n"}
        self.files["manifests/MANIFEST.json"] = json.dumps({
            "release": "2.1.0-core-rc1.4",
            "files": [
                {"path": name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
                for name, data in self.files.items()
            ],
        }).encode()
        for name, content in self.files.items():
            path = self.source / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        subprocess.run(["git", "init", "-q", str(self.source)], check=True)
        subprocess.run(["git", "-C", str(self.source), "add", "."], check=True)
        subprocess.run(["git", "-C", str(self.source), "-c", "user.name=CI", "-c", "user.email=ci@example.invalid", "commit", "-qm", "fixture"], check=True)
        self.sha = subprocess.check_output(["git", "-C", str(self.source), "rev-parse", "HEAD"], text=True).strip()
        self.kit = self.root / "kit.zip"
        self.required = tuple(self.files)

    def build(self, overrides=None, extra=None, manifest_sha=None, duplicate=False):
        contents = dict(self.files)
        contents["RELEASE-MANIFEST.txt"] = ("git_commit=" + (manifest_sha or self.sha) + "\nversion=2.1.0-core-rc1.4\n").encode()
        contents.update(overrides or {})
        lines = [hashlib.sha256(data).hexdigest() + "  ./" + name for name, data in contents.items()]
        with zipfile.ZipFile(self.kit, "w") as z:
            for name, data in contents.items():
                z.writestr(name, data)
            for name, data in extra or []:
                z.writestr(name, data)
            if duplicate:
                import warnings
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", UserWarning)
                    z.writestr("README.md", b"duplicate")
            z.writestr("FILES-SHA256SUMS", "\n".join(lines) + "\n")

    def audit(self, source=True):
        return audit_kit(self.kit, self.sha, self.source if source else None,
                         required_paths=self.required, alternative_groups={})

    def staged_manifest(self):
        stage = self.root / "stage"
        for name, content in self.files.items():
            path = stage / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        self.assertEqual(refresh(stage, "2.1.0-core-rc1.4"), 2)
        return json.loads((stage / "manifests/MANIFEST.json").read_text())

    def test_generated_staged_manifest_preserves_exact_source_provenance(self):
        staged = self.staged_manifest()
        self.build(overrides={"manifests/MANIFEST.json": json.dumps(staged).encode()})
        result = self.audit()
        self.assertEqual(result["status"], "PASS", result)
        self.assertEqual(result["source_files_verified"], 3)

    def test_generated_manifest_forged_source_release_fails(self):
        staged = self.staged_manifest()
        staged["source_manifest_release"] = "forged"
        self.build(overrides={"manifests/MANIFEST.json": json.dumps(staged).encode()})
        self.assertIn("STAGED_MANIFEST_SOURCE_PROVENANCE_MISMATCH", self.audit()["errors"])

    def test_generated_manifest_forged_file_order_fails(self):
        staged = self.staged_manifest()
        staged["files"].reverse()
        self.build(overrides={"manifests/MANIFEST.json": json.dumps(staged).encode()})
        self.assertIn("STAGED_MANIFEST_SOURCE_PROVENANCE_MISMATCH", self.audit()["errors"])

    def test_valid_inventory_with_exact_source(self):
        self.build()
        result = self.audit()
        self.assertEqual(result["status"], "PASS", result)
        self.assertEqual(result["checksums_verified"], 4)
        self.assertEqual(result["source_files_verified"], 3)

    def test_missing_migration_fails(self):
        self.build(overrides={"db/migrations/011_hitl_decision_outbox.sql": b""})
        # A placeholder migration is not proven functional, but a source mismatch is detected.
        self.assertIn("SOURCE_BLOB_MISMATCH:db/migrations/011_hitl_decision_outbox.sql", self.audit()["errors"])

    def test_manifest_commit_mismatch_fails(self):
        self.build(manifest_sha="0" * 40)
        self.assertIn("MANIFEST_SHA_MISMATCH", self.audit()["errors"])

    def test_stale_embedded_sha_fails_even_when_sha256sums_is_valid(self):
        embedded = json.loads(self.files["manifests/MANIFEST.json"])
        embedded["files"][0]["sha256"] = "0" * 64
        self.build(overrides={"manifests/MANIFEST.json": json.dumps(embedded).encode()})
        self.assertIn("EMBEDDED_FILE_SHA_MISMATCH:README.md", self.audit()["errors"])

    def test_stale_embedded_size_fails(self):
        embedded = json.loads(self.files["manifests/MANIFEST.json"])
        embedded["files"][0]["bytes"] += 1
        self.build(overrides={"manifests/MANIFEST.json": json.dumps(embedded).encode()})
        self.assertIn("EMBEDDED_FILE_SIZE_MISMATCH:README.md", self.audit()["errors"])

    def test_release_version_conflict_fails(self):
        embedded = json.loads(self.files["manifests/MANIFEST.json"])
        embedded["release"] = "8.0.0"
        self.build(overrides={"manifests/MANIFEST.json": json.dumps(embedded).encode()})
        self.assertIn("EMBEDDED_RELEASE_VERSION_MISMATCH", self.audit()["errors"])

    def test_invalid_embedded_manifest_fails(self):
        self.build(overrides={"manifests/MANIFEST.json": b"{broken"})
        self.assertIn("EMBEDDED_MANIFEST_UNREADABLE", self.audit()["errors"])

    def test_unchecksummed_file_fails(self):
        self.build(extra=[("untracked.txt", b"unverified")])
        self.assertIn("UNCHECKSUMMED_MEMBER:untracked.txt", self.audit()["errors"])

    def test_checksummed_untracked_member_fails_source_provenance(self):
        # Sidecar integrity alone does not prove that the member belongs to HEAD.
        self.build(overrides={"foreign.txt": b"not in git HEAD"})
        result = self.audit()
        self.assertIn("SOURCE_MEMBER_UNTRACKED:foreign.txt", result["errors"])

    def test_non_required_tracked_member_must_match_head(self):
        path = self.source / "notes.txt"
        path.write_bytes(b"tracked source\\n")
        subprocess.run(["git", "-C", str(self.source), "add", "notes.txt"], check=True)
        subprocess.run(["git", "-C", str(self.source), "-c", "user.name=CI",
                        "-c", "user.email=ci@example.invalid",
                        "commit", "-qm", "add non-required source"], check=True)
        self.sha = subprocess.check_output(
            ["git", "-C", str(self.source), "rev-parse", "HEAD"], text=True).strip()
        self.build(overrides={"notes.txt": b"modified in package\\n"})
        result = self.audit()
        self.assertIn("SOURCE_BLOB_MISMATCH:notes.txt", result["errors"])

    def test_non_required_tracked_member_matching_head_passes(self):
        path = self.source / "notes.txt"
        path.write_bytes(b"tracked source\\n")
        subprocess.run(["git", "-C", str(self.source), "add", "notes.txt"], check=True)
        subprocess.run(["git", "-C", str(self.source), "-c", "user.name=CI",
                        "-c", "user.email=ci@example.invalid",
                        "commit", "-qm", "add non-required source"], check=True)
        self.sha = subprocess.check_output(
            ["git", "-C", str(self.source), "rev-parse", "HEAD"], text=True).strip()
        self.build(overrides={"notes.txt": b"tracked source\\n"})
        result = self.audit()
        self.assertEqual(result["status"], "PASS", result)
        self.assertEqual(result["source_files_verified"], 4)

    def test_zip_slip_member_fails(self):
        self.build(extra=[("../escape.txt", b"bad")])
        self.assertIn("UNSAFE_MEMBER_PATH:../escape.txt", self.audit()["errors"])

    def test_duplicate_member_fails(self):
        self.build(duplicate=True)
        self.assertIn("DUPLICATE_MEMBERS", self.audit()["errors"])

    def test_missing_checkout_fails(self):
        self.build()
        self.assertIn("SOURCE_TREE_NOT_PROVIDED", self.audit(source=False)["errors"])

    def test_dirty_checkout_cannot_masquerade_as_exact_head(self):
        changed = b"locally modified source, not committed\\n"
        (self.source / "README.md").write_bytes(changed)
        self.build(overrides={"README.md": changed})
        # The archive and checkout bytes match, but neither is the Git HEAD.
        result = self.audit()
        self.assertIn("SOURCE_TREE_DIRTY", result["errors"])

    def test_nested_source_directory_is_not_repository_root(self):
        self.build()
        nested = self.source / "db"
        result = audit_kit(self.kit, self.sha, nested,
                           required_paths=self.required, alternative_groups={})
        self.assertIn("SOURCE_NOT_REPOSITORY_ROOT", result["errors"])

    def test_source_head_mismatch_fails(self):
        self.build()
        result = audit_kit(self.kit, "1" * 40, self.source,
                           required_paths=self.required, alternative_groups={})
        self.assertIn("SOURCE_HEAD_MISMATCH", result["errors"])

    def test_missing_required_path_fails(self):
        self.build()
        result = audit_kit(self.kit, self.sha, self.source,
                           required_paths=self.required + ("app/core/hitl_identity.py",), alternative_groups={})
        self.assertIn("REQUIRED_MISSING:app/core/hitl_identity.py", result["errors"])

    def test_missing_rollback_entrypoint_fails(self):
        self.build()
        result = audit_kit(self.kit, self.sha, self.source,
                           required_paths=self.required,
                           alternative_groups={"rollback_entrypoint": ("deploy/rollback.sh",)})
        self.assertIn("ENTRYPOINT_MISSING:rollback_entrypoint", result["errors"])

    def test_read_only_audit_tool_does_not_qualify_install_or_rollback(self):
        self.build(overrides={"deploy/aiops_release.py": b"# read-only audit\\n"})
        result = audit_kit(self.kit, self.sha, self.source,
                           required_paths=self.required)
        self.assertIn("ENTRYPOINT_MISSING:install_entrypoint", result["errors"])
        self.assertIn("ENTRYPOINT_MISSING:upgrade_entrypoint", result["errors"])
        self.assertIn("ENTRYPOINT_MISSING:rollback_entrypoint", result["errors"])

    def test_partial_p0_transaction_does_not_qualify_cumulative_rollback(self):
        self.build(overrides={"deploy/deploy-acme-p0.py": b"# partial P0 only\\n"})
        result = audit_kit(self.kit, self.sha, self.source,
                           required_paths=self.required)
        self.assertIn("ENTRYPOINT_MISSING:rollback_entrypoint", result["errors"])

    def test_install_entrypoint_without_rollback_is_blocked(self):
        self.build(overrides={"deploy/install.sh": b"#!/bin/sh\\nexit 1\\n"})
        result = audit_kit(self.kit, self.sha, self.source,
                           required_paths=self.required)
        self.assertNotIn("ENTRYPOINT_MISSING:install_entrypoint", result["errors"])
        self.assertIn("ENTRYPOINT_MISSING:upgrade_entrypoint", result["errors"])
        self.assertIn("ENTRYPOINT_MISSING:rollback_entrypoint", result["errors"])



if __name__ == "__main__":
    unittest.main()
