"""Offline candidate verifier regression tests; synthetic data only."""
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from deploy import single_portal_candidate_kit as builder
from deploy import verify_single_portal_candidate_kit as verifier

COMMIT = "a" * 40


class VerifyCandidateTests(unittest.TestCase):
    def make_kit(self, root):
        names = sorted(builder.APPROVED)
        for name in names:
            file = root / name
            file.parent.mkdir(parents=True, exist_ok=True)
            if name == "demo/noc_platform_registry.py":
                components = tuple((f"svc-{n}", f"Service {n}", f"/service/{n}", "engine") for n in range(20))
                file.write_text("COMPONENTS=" + repr(components) + "\n", encoding="utf-8")
            else:
                file.write_text("# synthetic source fixture\n", encoding="utf-8")
        output = root.parent / "candidate.zip"
        with patch.object(builder, "source_paths", return_value=(COMMIT, names)):
            builder.build(root, output, COMMIT)
        return output, names

    def mutate(self, archive, name, transform, *, resign=False):
        with zipfile.ZipFile(archive) as z:
            contents = {n: z.read(n) for n in z.namelist()}
        contents[name] = transform(contents[name])
        if resign:
            contents["metadata/SHA256SUMS"] = "".join(
                f"{builder.sha256(contents[n])}  {n}\n"
                for n in sorted(contents) if n != "metadata/SHA256SUMS").encode()
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
            for n, content in contents.items():
                z.writestr(n, content)

    def test_valid_candidate_and_pinned_checkout(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"; root.mkdir()
            archive, names = self.make_kit(root)
            self.assertFalse(verifier.verify(archive)["checkout_provenance_verified"])
            with patch.object(verifier, "source_paths", return_value=(COMMIT, names)):
                result = verifier.verify(archive, root)
            self.assertTrue(result["checkout_provenance_verified"])
            self.assertFalse(result["production_qualified"])
            self.assertEqual(result["routes_unverified"], 20)

    def test_detect_corrupt_checksum(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"; root.mkdir()
            archive, _ = self.make_kit(root)
            self.mutate(archive, "metadata/README.md", lambda b: b + b"changed")
            with self.assertRaisesRegex(ValueError, "checksum"):
                verifier.verify(archive)

    def test_detect_forged_embedded_source_even_if_resigned(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"; root.mkdir()
            archive, _ = self.make_kit(root)
            self.mutate(archive, "sources/demo/noc_platform_registry.py", lambda b: b + b"# forged\n", resign=True)
            with self.assertRaisesRegex(ValueError, "embedded source provenance"):
                verifier.verify(archive)

    def test_detect_forged_route_even_if_resigned(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"; root.mkdir()
            archive, _ = self.make_kit(root)
            def forged(b):
                x = json.loads(b); x["routes"][0]["route_mounted"] = True
                return json.dumps(x).encode()
            self.mutate(archive, "metadata/planned-routes.json", forged, resign=True)
            with self.assertRaisesRegex(ValueError, "route attestation"):
                verifier.verify(archive)

    def test_reject_production_claim_even_if_resigned(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"; root.mkdir()
            archive, _ = self.make_kit(root)
            def forged(b):
                x = json.loads(b); x["production_qualified"] = True
                return json.dumps(x).encode()
            self.mutate(archive, "metadata/source-manifest.json", forged, resign=True)
            with self.assertRaisesRegex(ValueError, "status or schema"):
                verifier.verify(archive)

    def test_reject_embedded_secret_even_if_resigned(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"; root.mkdir()
            archive, _ = self.make_kit(root)
            def forged(b):
                x = json.loads(b)
                for row in x["source_inventory"]:
                    if row["path"] == builder.APPROVED[0]:
                        row["sha256"] = builder.sha256(b"-----BEGIN PRIVATE KEY-----\nsecret")
                        row["bytes"] = len(b"-----BEGIN PRIVATE KEY-----\nsecret")
                return json.dumps(x).encode()
            self.mutate(archive, "sources/" + builder.APPROVED[0], lambda b: b"-----BEGIN PRIVATE KEY-----\nsecret")
            self.mutate(archive, "metadata/source-manifest.json", forged, resign=True)
            with self.assertRaisesRegex(ValueError, "sensitive embedded"):
                verifier.verify(archive)

    def test_unembedded_source_requires_checkout_to_attest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"; root.mkdir()
            archive, names = self.make_kit(root)
            extra = "demo/not_embedded.py"
            (root / extra).write_text("# synthetic extra\n", encoding="utf-8")
            def forged(b):
                x = json.loads(b)
                x["source_inventory"].append({"path": extra, "sha256": "b" * 64,
                                              "bytes": 18, "embedded": False})
                return json.dumps(x).encode()
            self.mutate(archive, "metadata/source-manifest.json", forged, resign=True)
            self.assertFalse(verifier.verify(archive)["checkout_provenance_verified"])
            with patch.object(verifier, "source_paths", return_value=(COMMIT, names + [extra])):
                with self.assertRaisesRegex(ValueError, "checkout source mismatch"):
                    verifier.verify(archive, root)

    def test_reject_duplicate_zip_members(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"; root.mkdir()
            archive, _ = self.make_kit(root)
            with zipfile.ZipFile(archive, "a") as z:
                import warnings
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", UserWarning)
                    z.writestr("metadata/README.md", b"duplicate")
            with self.assertRaisesRegex(ValueError, "duplicate"):
                verifier.verify(archive)


if __name__ == "__main__":
    unittest.main()
