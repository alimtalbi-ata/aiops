"""Synthetic, non-mutating tests for the kit CLI planner."""
import pathlib
import tempfile
import unittest
from kit_cli_dry_run import ACTIONS, IMAGE_KEYS, plan

IMAGES = {k + "_IMAGE": "example.invalid/" + k.lower() + "@sha256:" + "a" * 64
          for k in IMAGE_KEYS}


class KitCliDryRunTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.compose = pathlib.Path(self.temp.name) / "docker-compose.yml"
        self.compose.write_text("services: {}\n")

    def test_every_action_is_nonexecuting(self):
        for action in ACTIONS:
            with self.subTest(action=action):
                p = plan(action, "default", IMAGES, self.compose)
                self.assertFalse(p["executes"])
                self.assertFalse(p["production_authorized"])
                self.assertFalse(p["oci_provenance_verified"])
                self.assertEqual(p["command_prefix"][:4], ["docker", "compose", "-f", str(self.compose)])

    def test_demo_profile(self):
        p = plan("preflight", "demo", IMAGES, self.compose)
        self.assertEqual(p["command_prefix"][-2:], ["--profile", "demo"])

    def test_missing_required_image_fails_closed(self):
        images = dict(IMAGES)
        del images["CORE_IMAGE"]
        with self.assertRaisesRegex(ValueError, "CORE_IMAGE"):
            plan("install", "default", images, self.compose)

    def test_default_does_not_require_demo_image(self):
        images = dict(IMAGES)
        del images["DEMO_IMAGE"]
        self.assertEqual(plan("health", "default", images, self.compose)["profile"], "default")
        with self.assertRaisesRegex(ValueError, "DEMO_IMAGE"):
            plan("health", "demo", images, self.compose)

    def test_tag_only_is_rejected(self):
        images = dict(IMAGES, CORE_IMAGE="example.invalid/core:latest")
        with self.assertRaises(ValueError):
            plan("install", "default", images, self.compose)

    def test_wrong_compose_name_is_rejected(self):
        wrong = pathlib.Path(self.temp.name) / "compose.override.yml"
        wrong.write_text("services: {}\n")
        with self.assertRaises(ValueError):
            plan("install", "default", IMAGES, wrong)

    def test_unknown_action_and_profile_rejected(self):
        for action, profile in [("deploy", "default"), ("install", "production")]:
            with self.assertRaises(ValueError):
                plan(action, profile, IMAGES, self.compose)


if __name__ == "__main__":
    unittest.main()
