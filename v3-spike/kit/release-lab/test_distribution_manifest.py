"""Real OpenSSL Ed25519 tests with disposable keys, never release credentials."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from distribution_manifest import canonical, create, sha, verify

SOURCE = "a" * 40
D = ["sha256:" + str(i) * 64 for i in range(1, 5)]
REGISTRY = "docker.io/library/registry@sha256:" + "5" * 64


class DistributionTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.manifest = self.root / "manifest.json"
        self.key = self.root / "private.pem"
        self.public = self.root / "public.der"
        self.sig = self.root / "manifest.sig"
        self.make_key(self.key, self.public)
        self.trust = sha(self.public.read_bytes())
        create(self.manifest, SOURCE, *D, REGISTRY)
        self.sign()

    def openssl(self, *args):
        subprocess.run(["openssl", *map(str, args)], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)

    def make_key(self, private, public):
        self.openssl("genpkey", "-algorithm", "ED25519", "-out", private)
        self.openssl("pkey", "-in", private, "-pubout", "-outform", "DER", "-out", public)

    def sign(self, key=None):
        self.openssl("pkeyutl", "-sign", "-rawin", "-inkey", key or self.key,
                     "-in", self.manifest, "-out", self.sig)

    def check(self, trust=None, source=SOURCE):
        return verify(self.manifest, self.sig, self.public, trust or self.trust, source)

    def mutate(self, field, value, resign=False):
        doc = json.loads(self.manifest.read_bytes())
        doc[field] = value
        self.manifest.write_bytes(canonical(doc))
        if resign:
            self.sign()

    def test_valid(self):
        receipt = self.check()
        self.assertEqual(receipt["result"], "PASS")
        self.assertEqual(receipt["statement"]["archive_sha256"], D[1])
        self.assertFalse(receipt["production_authorized"])

    def test_tampered_archive(self):
        self.mutate("archive_sha256", D[0])
        with self.assertRaises(ValueError): self.check()

    def test_tampered_support(self):
        self.mutate("support_manifest_sha256", D[0])
        with self.assertRaises(ValueError): self.check()

    def test_tampered_signature(self):
        sig = self.sig.read_bytes()
        self.sig.write_bytes(bytes([sig[0] ^ 1]) + sig[1:])
        with self.assertRaises(ValueError): self.check()

    def test_substitute_key_and_signature(self):
        other = self.root / "other.pem"
        self.make_key(other, self.public)
        self.sign(other)
        with self.assertRaises(ValueError): self.check()

    def test_wrong_trust_anchor(self):
        with self.assertRaises(ValueError): self.check(trust=D[0])

    def test_wrong_source(self):
        with self.assertRaises(ValueError): self.check(source="b" * 40)

    def test_signed_production_scope_refused(self):
        self.mutate("production_authorized", True, True)
        with self.assertRaises(ValueError): self.check()

    def test_signed_extra_field_refused(self):
        self.mutate("extra", "unexpected", True)
        with self.assertRaises(ValueError): self.check()

    def test_signed_duplicate_key_refused(self):
        raw = self.manifest.read_bytes()
        self.manifest.write_bytes(b'{"schema_version":1,' + raw[1:])
        self.sign()
        with self.assertRaises(ValueError): self.check()

    def test_signed_unpinned_registry_refused(self):
        self.mutate("registry_reference", "registry:2", True)
        with self.assertRaises(ValueError): self.check()

    def test_truncated_signature_refused(self):
        self.sig.write_bytes(self.sig.read_bytes()[:-1])
        with self.assertRaises(ValueError): self.check()

    def test_link_refused(self):
        other = self.root / "other.sig"
        self.sig.rename(other)
        self.sig.symlink_to(other)
        with self.assertRaises(OSError): self.check()

    def test_exclusive_create(self):
        before = self.manifest.read_bytes()
        with self.assertRaises(FileExistsError):
            create(self.manifest, SOURCE, *D, REGISTRY)
        self.assertEqual(self.manifest.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
