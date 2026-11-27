"""Synthetic index binding tests; a real scanner smoke is separate in CI."""
import json
from pathlib import Path
import tempfile
import unittest
from oci_transport import SERVICES, digest
from sbom_contract import SYFT_VERSION, SYFT_ARCHIVE_SHA, verify, read_report


def encode(value):
    return json.dumps(value, sort_keys=True).encode()


class SBOMTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.bom_path = self.root / "bom.json"
        self.out = self.root / "sbom"
        self.out.mkdir()
        images = {}
        rows = {}
        for i, service in enumerate(sorted(SERVICES), 1):
            d = "sha256:" + format(i, "064x")
            image = {"manifest_digest": d, "config_digest": d, "engine_image_id": d,
                     "reference": "127.0.0.1:15080/aiops-v3/" + service + "@" + d,
                     "os": "linux", "architecture": "amd64"}
            images[service] = image
            raw = encode({"spdxVersion": "SPDX-2.3", "SPDXID": "SPDXRef-DOCUMENT", "dataLicense": "CC0-1.0",
                          "creationInfo": {"creators": ["Tool: syft-" + SYFT_VERSION]},
                          "packages": [{"SPDXID": "SPDXRef-Package-" + service, "name": service}]})
            (self.out / (service + ".spdx.json")).write_bytes(raw)
            rows[service] = {k: image[k] for k in ("reference", "manifest_digest", "config_digest", "engine_image_id")}
            rows[service].update(report_sha256=digest(raw), packages=1)
        self.bom_path.write_bytes(encode({"schema_version": 1, "classification": "DISPOSABLE_POC_E17_IMAGE_BOM",
                                         "source_sha": "a"*40, "production_authorized": False, "images": images}))
        self.index = {"classification": "V3_E17_LAB_SBOM_INDEX", "result": "PASS", "source_sha": "a"*40,
                      "bom_sha256": digest(self.bom_path.read_bytes()),
                      "scanner": {"name": "syft", "version": SYFT_VERSION, "archive_sha256": SYFT_ARCHIVE_SHA},
                      "images": rows, "vulnerability_scan": "NOT_RUN", "production_authorized": False}
        self.save()
        self.report = self.out / "core.spdx.json"

    def save(self):
        (self.out/"index.json").write_bytes(encode(self.index))

    def check(self):
        return verify(self.bom_path, self.out)

    def rejected(self):
        with self.assertRaises(ValueError):
            self.check()

    def alter_report(self, callback, rebind=False):
        doc = json.loads(self.report.read_bytes())
        callback(doc)
        raw = encode(doc)
        self.report.write_bytes(raw)
        if rebind:
            self.index["images"]["core"]["report_sha256"] = digest(raw)
            self.index["images"]["core"]["packages"] = len(doc["packages"])
            self.save()

    def test_roundtrip(self):
        self.assertEqual(self.check(), self.index)
        self.assertEqual(len(self.index["images"]), 10)

    def test_tampered_report(self):
        self.alter_report(lambda d: d["packages"][0].update(name="changed"))
        self.rejected()

    def test_wrong_manifest(self):
        self.index["images"]["core"]["manifest_digest"] = "sha256:"+"f"*64
        self.save(); self.rejected()

    def test_wrong_config(self):
        self.index["images"]["core"]["config_digest"] = "sha256:"+"f"*64
        self.save(); self.rejected()

    def test_wrong_bom(self):
        self.index["bom_sha256"] = "sha256:"+"f"*64
        self.save(); self.rejected()

    def test_missing_report(self):
        self.report.unlink(); self.rejected()

    def test_extra_report(self):
        (self.out/"unexpected.json").write_text("{}"); self.rejected()

    def test_duplicate_package(self):
        self.alter_report(lambda d: d["packages"].append(d["packages"][0]), True)
        self.rejected()

    def test_empty_packages(self):
        self.alter_report(lambda d: d.update(packages=[]), True)
        self.rejected()

    def test_wrong_scanner(self):
        self.alter_report(lambda d: d["creationInfo"].update(creators=["Tool: other-1"]), True)
        self.rejected()

    def test_wrong_scanner_prefix(self):
        self.alter_report(lambda d: d["creationInfo"].update(creators=["Tool: syft-"+SYFT_VERSION+"9"]), True)
        self.rejected()

    def test_production_scope(self):
        self.index["production_authorized"] = True
        self.save(); self.rejected()

    def test_false_cve_claim(self):
        self.index["vulnerability_scan"] = "PASS"
        self.save(); self.rejected()

    def test_linked_report(self):
        other = self.root/"outside.json"
        self.report.rename(other); self.report.symlink_to(other)
        self.rejected()

if __name__ == "__main__":
    unittest.main()
