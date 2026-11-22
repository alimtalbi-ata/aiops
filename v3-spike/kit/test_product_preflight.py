"""Synthetic product BOM negative tests. No client data, Docker, or host changes."""
import unittest
from product_preflight import REQUIRED, validate

def valid():
    return {"schema": 1, "services": {
        name: {"image": "example.org/v3/" + name + "@sha256:" + "a" * 64,
               "profile": "default", "secrets": ["LOCAL_SECRET_REF"],
               "migration": name == "core"}
        for name in REQUIRED
    }}

class ProductPreflightTests(unittest.TestCase):
    def test_valid_static(self):
        self.assertFalse(validate(valid())["runtime_attested"])
    def test_missing_service(self):
        b = valid(); del b["services"]["evidence"]
        self.assertRaises(ValueError, validate, b)
    def test_mutable_tag(self):
        b = valid(); b["services"]["gamma"]["image"] = "example.org/v3/gamma:latest"
        self.assertRaises(ValueError, validate, b)
    def test_missing_migration(self):
        b = valid(); b["services"]["core"]["migration"] = False
        self.assertRaises(ValueError, validate, b)
    def test_bad_profile(self):
        b = valid(); b["services"]["worker"]["profile"] = "demo"
        self.assertRaises(ValueError, validate, b)
    def test_secret_value_not_reference(self):
        b = valid(); b["services"]["policy"]["secrets"] = ["password=abc"]
        self.assertRaises(ValueError, validate, b)
    def test_unknown_field(self):
        b = valid(); b["services"]["core"]["privileged"] = True
        self.assertRaises(ValueError, validate, b)
    def test_duplicate_secret_reference(self):
        b = valid(); b["services"]["hitl"]["secrets"] = ["X", "X"]
        self.assertRaises(ValueError, validate, b)

if __name__ == "__main__":
    unittest.main()
