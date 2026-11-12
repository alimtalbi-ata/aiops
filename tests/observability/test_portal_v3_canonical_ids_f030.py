"""F-030 synthetic Docker identity shape gate. Not wired to collector or deployment.
Require full IDs from docker image ls --no-trunc and docker ps -a --no-trunc.
Do not infer host provenance, tenant ACL, or CI from this helper.
"""
import re
import unittest

IMAGE = re.compile(r"sha256:[0-9a-f]{64}\Z")
CONTAINER = re.compile(r"[0-9a-f]{64}\Z")

def canonical_identity_gate(report):
    if not isinstance(report, dict) or report.get("complete") is not True:
        return "NO_GO:INVENTORY_UNVERIFIED"
    for kind, pattern in (("images", IMAGE), ("containers", CONTAINER)):
        rows, count = report.get(kind), report.get(kind + "_count")
        if not isinstance(rows, list) or type(count) is not int or count < 0:
            return "NO_GO:COUNT_UNKNOWN"
        if count != len(rows):
            return "NO_GO:INVENTORY_INCOMPLETE"
        if any(not isinstance(x, str) or not pattern.fullmatch(x) for x in rows):
            return "NO_GO:NONCANONICAL_ID"
        if len(set(rows)) != len(rows):
            return "NO_GO:DUPLICATE_IDENTITY"
    return "IDENTITY_SHAPE_ELIGIBLE_NOT_DEPLOY_APPROVAL"

class TestCanonicalIdentity(unittest.TestCase):
    def setUp(self):
        self.report = {"complete": True, "images": ["sha256:" + "a"*64],
                       "images_count": 1, "containers": ["b"*64], "containers_count": 1}
    def test_valid_not_deploy_approval(self):
        self.assertEqual(canonical_identity_gate(self.report), "IDENTITY_SHAPE_ELIGIBLE_NOT_DEPLOY_APPROVAL")
    def test_short_image_id_rejected(self):
        self.report["images"] = ["sha256:" + "a"*12]
        self.assertEqual(canonical_identity_gate(self.report), "NO_GO:NONCANONICAL_ID")
    def test_short_container_id_rejected(self):
        self.report["containers"] = ["b"*12]
        self.assertEqual(canonical_identity_gate(self.report), "NO_GO:NONCANONICAL_ID")
    def test_image_tag_rejected(self):
        self.report["images"] = ["portal:v3"]
        self.assertEqual(canonical_identity_gate(self.report), "NO_GO:NONCANONICAL_ID")
    def test_uppercase_and_whitespace_rejected(self):
        for invalid in ["sha256:"+"A"*64, " sha256:"+"a"*64, "sha256:"+"a"*64+"\n"]:
            with self.subTest(invalid=invalid):
                self.report["images"] = [invalid]
                self.assertEqual(canonical_identity_gate(self.report), "NO_GO:NONCANONICAL_ID")
    def test_duplicate_full_ids_rejected(self):
        self.report["images"] *= 2
        self.report["images_count"] = 2
        self.assertEqual(canonical_identity_gate(self.report), "NO_GO:DUPLICATE_IDENTITY")
    def test_boolean_count_rejected(self):
        self.report["containers_count"] = True
        self.assertEqual(canonical_identity_gate(self.report), "NO_GO:COUNT_UNKNOWN")
    def test_missing_complete_rejected(self):
        del self.report["complete"]
        self.assertEqual(canonical_identity_gate(self.report), "NO_GO:INVENTORY_UNVERIFIED")

if __name__ == "__main__":
    unittest.main()
