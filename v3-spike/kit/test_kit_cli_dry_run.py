"""Synthetic, non-mutating tests for the kit CLI planner."""
import pathlib
import re
import tempfile
import unittest
from kit_cli_dry_run import ACTIONS, IMAGE_KEYS, COMPOSE, plan

IMAGES = {k + "_IMAGE": "example.invalid/" + k.lower() + "@sha256:" + "a" * 64
          for k in IMAGE_KEYS}


class KitCliDryRunTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.compose = COMPOSE

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

    def test_same_basename_outside_canonical_path_rejected(self):
        alternate = pathlib.Path(self.temp.name) / "docker-compose.yml"
        alternate.write_text("services: {}\n")
        with self.assertRaisesRegex(ValueError, "canonical"):
            plan("install", "default", IMAGES, alternate)

    def test_product_compose_exact_service_contract(self):
        source = COMPOSE.read_text(encoding="utf-8")
        services = source.split("services:", 1)[1].split("\nnetworks:", 1)[0]
        found = set(re.findall(r"^  ([a-z][a-z0-9_-]*):\s*$", services, re.M))
        self.assertEqual(found, {"core", "temporal", "worker", "policy", "hitl", "evidence", "gamma", "demo"})
        self.assertIn("    profiles: [demo]", services)
        self.assertEqual(services.count("    profiles:"), 1)

    def test_product_compose_exact_image_keys(self):
        source = COMPOSE.read_text(encoding="utf-8")
        found = set(re.findall(r"\$\{([A-Z]+_IMAGE):\?", source))
        self.assertEqual(found, {key + "_IMAGE" for key in IMAGE_KEYS if key != "DEMO"})
        self.assertRegex(source, r"\$\{DEMO_IMAGE:-registry\.invalid/disabled-demo@sha256:0{64}\}")
        self.assertEqual(source.count("    image: ${"), len(IMAGE_KEYS))

    def test_product_compose_single_file_and_no_unsafe_host_ports(self):
        source = COMPOSE.read_text(encoding="utf-8")
        self.assertNotRegex(source, r"(?m)^\s*(include|extends|network_mode|privileged):")
        self.assertIn("127.0.0.1:18080:8080", source)
        self.assertNotRegex(source, r"(?m)^\s*-?\s*(?:0\.0\.0\.0:)?(?:7770|7777|7790):")
        self.assertIn("    internal: true", source)

    def test_optional_demo_interpolation_requires_explicit_demo_planner_image(self):
        source = COMPOSE.read_text(encoding="utf-8")
        self.assertNotIn("${DEMO_IMAGE:?", source)
        self.assertIn("${DEMO_IMAGE:-registry.invalid/disabled-demo@sha256:", source)
        without_demo = {k: v for k, v in IMAGES.items() if k != "DEMO_IMAGE"}
        self.assertEqual(plan("preflight", "default", without_demo)["profile"], "default")
        with self.assertRaisesRegex(ValueError, "DEMO_IMAGE"):
            plan("preflight", "demo", without_demo)

    def test_unknown_action_and_profile_rejected(self):
        for action, profile in [("deploy", "default"), ("install", "production")]:
            with self.assertRaises(ValueError):
                plan(action, profile, IMAGES, self.compose)


if __name__ == "__main__":
    unittest.main()
