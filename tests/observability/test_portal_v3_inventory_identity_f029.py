"""F-029: negative tests for duplicate/blank rootless inventory identifiers.
Synthetic only; no Docker, network or host access. NOT a deployment gate.
"""
import unittest

def inventory_identity_gate(report):
    if not isinstance(report, dict) or report.get("complete") is not True:
        return "NO_GO:INVENTORY_UNVERIFIED"
    for kind in ("images", "containers"):
        rows = report.get(kind)
        count = report.get(kind + "_count")
        if not isinstance(rows, list) or type(count) is not int or count < 0:
            return "NO_GO:COUNT_UNKNOWN"
        if count != len(rows):
            return "NO_GO:INVENTORY_INCOMPLETE"
        # IDs must be immutable canonical identifiers; names/tags are not identities.
        if any(not isinstance(x, str) or not x.strip() for x in rows):
            return "NO_GO:IDENTITY_UNKNOWN"
        if len(set(rows)) != len(rows):
            return "NO_GO:DUPLICATE_IDENTITY"
    return "INVENTORY_IDENTITIES_ELIGIBLE_NOT_DEPLOY_APPROVAL"

class NegativeInventoryIdentity(unittest.TestCase):
    def setUp(self):
        self.r = dict(complete=True, images=["sha256:a", "sha256:b"],
                      images_count=2, containers=["abc", "def"], containers_count=2)
    def test_unique(self):
        self.assertEqual(inventory_identity_gate(self.r), "INVENTORY_IDENTITIES_ELIGIBLE_NOT_DEPLOY_APPROVAL")
    def test_duplicate_images(self):
        self.r["images"] = ["sha256:a", "sha256:a"]
        self.assertEqual(inventory_identity_gate(self.r), "NO_GO:DUPLICATE_IDENTITY")
    def test_duplicate_containers(self):
        self.r["containers"] = ["abc", "abc"]
        self.assertEqual(inventory_identity_gate(self.r), "NO_GO:DUPLICATE_IDENTITY")
    def test_blank_identity(self):
        self.r["images"] = ["sha256:a", ""]
        self.assertEqual(inventory_identity_gate(self.r), "NO_GO:IDENTITY_UNKNOWN")
    def test_count_mismatch(self):
        self.r["images_count"] = 210
        self.assertEqual(inventory_identity_gate(self.r), "NO_GO:INVENTORY_INCOMPLETE")
    def test_boolean_count(self):
        self.r["images_count"] = True
        self.assertEqual(inventory_identity_gate(self.r), "NO_GO:COUNT_UNKNOWN")
    def test_missing_completeness(self):
        self.r.pop("complete")
        self.assertEqual(inventory_identity_gate(self.r), "NO_GO:INVENTORY_UNVERIFIED")

if __name__ == "__main__":
    unittest.main()
