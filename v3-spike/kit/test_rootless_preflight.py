"""Synthetic rootless preflight regressions; no Docker invocation."""
import importlib.util
import json
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("rootless_preflight", Path(__file__).with_name("rootless_preflight.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class RootlessPreflightTests(unittest.TestCase):
    def setUp(self):
        self.root = Path("/srv/aiops-v3")
        self.info = {"SecurityOptions": ["name=seccomp", "name=rootless"],
                     "DockerRootDir": "/srv/aiops-v3/docker-data"}
        self.graph = {"services": {k.lower(): {"volumes": []} for k in module.IMAGE_KEYS}, "volumes": {}}

    def test_rootless_valid(self):
        module.validate_daemon(self.info, f"unix:///run/user/{module.os.getuid()}/docker.sock", module.os.getuid(), self.root)

    def test_rootful_rejected(self):
        self.info["SecurityOptions"] = ["name=seccomp"]
        with self.assertRaisesRegex(ValueError, "not attested rootless"):
            module.validate_daemon(self.info, f"unix:///run/user/{module.os.getuid()}/docker.sock", module.os.getuid(), self.root)

    def test_rootful_socket_rejected(self):
        with self.assertRaisesRegex(ValueError, "rootless socket"):
            module.validate_daemon(self.info, "unix:///var/run/docker.sock", module.os.getuid(), self.root)

    def test_data_root_escape_rejected(self):
        self.info["DockerRootDir"] = "/var/lib/docker"
        with self.assertRaisesRegex(ValueError, "inside installation root"):
            module.validate_daemon(self.info, f"unix:///run/user/{module.os.getuid()}/docker.sock", module.os.getuid(), self.root)

    def test_bind_escape_rejected(self):
        self.graph["services"]["core"]["volumes"] = [{"type": "bind", "source": "/etc", "target": "/etc"}]
        with self.assertRaisesRegex(ValueError, "escapes"):
            module.validate_compose(self.graph, self.root, "default")

    def test_external_volume_rejected(self):
        self.graph["volumes"] = {"data": {"external": True}}
        with self.assertRaisesRegex(ValueError, "external"):
            module.validate_compose(self.graph, self.root, "default")

    def test_default_service_graph_accepted(self):
        module.validate_compose(self.graph, self.root, "default")

    def test_demo_requires_demo_service(self):
        with self.assertRaisesRegex(ValueError, "service set"):
            module.validate_compose(self.graph, self.root, "demo")

    def test_digest_missing_rejected(self):
        with self.assertRaisesRegex(ValueError, "references missing"):
            module.validate_images({}, "default")

    def test_relative_root_rejected(self):
        with self.assertRaisesRegex(ValueError, "absolute"):
            module.validate_root("aiops-v3")


if __name__ == "__main__":
    unittest.main()
