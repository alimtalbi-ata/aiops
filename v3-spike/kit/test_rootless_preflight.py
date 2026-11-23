"""Synthetic rootless preflight regressions; no Docker invocation."""
import importlib.util
import copy
import json
import tempfile
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
        self.graph = {"services": {k.lower(): {"volumes": [], "read_only": True, "cap_drop": ["ALL"],
                          "security_opt": ["no-new-privileges:true"], "ports": []} for k in module.IMAGE_KEYS}, "volumes": {}}
        self.graph["services"]["gamma"]["ports"] = [{"host_ip": "127.0.0.1", "published": "18080", "target": 8080}]

    def test_rootless_spoof_rejected(self):
        for spoof in ("name=not-rootless", "name=rootless-disabled", "notrootless", "name=ROOTLESS-extra"):
            with self.subTest(spoof=spoof):
                self.info["SecurityOptions"] = [spoof]
                with self.assertRaisesRegex(ValueError, "not attested rootless"):
                    module.validate_daemon(self.info, f"unix:///run/user/{module.os.getuid()}/docker.sock", module.os.getuid(), self.root)

    def test_root_symlink_ancestor_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            (base / "real").mkdir()
            (base / "alias").symlink_to(base / "real", target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "symlinks"):
                module.validate_root(base / "alias" / "install")

    def test_real_root_ancestor_accepted(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "install"
            self.assertEqual(module.validate_root(root), root.resolve())

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

    def test_hardening_mutations_rejected(self):
        mutations = (
            ("read_only", False, "read_only"),
            ("cap_drop", [], "cap_drop"),
            ("security_opt", [], "no-new-privileges"),
        )
        for field, value, message in mutations:
            with self.subTest(field=field):
                graph = copy.deepcopy(self.graph)
                graph["services"]["core"][field] = value
                with self.assertRaisesRegex(ValueError, message):
                    module.validate_compose(graph, self.root, "default")

    def test_undeclared_named_volume_rejected(self):
        graph = copy.deepcopy(self.graph)
        graph["services"]["core"]["volumes"] = [{"type": "volume", "source": "missing", "target": "/data"}]
        with self.assertRaisesRegex(ValueError, "undeclared"):
            module.validate_compose(graph, self.root, "default")

    def test_read_write_bind_rejected(self):
        graph = copy.deepcopy(self.graph)
        graph["services"]["core"]["volumes"] = [{"type": "bind", "source": "/srv/aiops-v3/data", "target": "/data"}]
        with self.assertRaisesRegex(ValueError, "read-only"):
            module.validate_compose(graph, self.root, "default")

    def test_non_gamma_published_port_rejected(self):
        graph = copy.deepcopy(self.graph)
        graph["services"]["core"]["ports"] = [{"host_ip": "127.0.0.1", "published": "19000", "target": 9000}]
        with self.assertRaisesRegex(ValueError, "only GAMMA"):
            module.validate_compose(graph, self.root, "default")

    def test_gamma_public_port_rejected(self):
        graph = copy.deepcopy(self.graph)
        graph["services"]["gamma"]["ports"][0]["host_ip"] = "0.0.0.0"
        with self.assertRaisesRegex(ValueError, "loopback-only"):
            module.validate_compose(graph, self.root, "default")

    def test_declared_named_volume_accepted(self):
        graph = copy.deepcopy(self.graph)
        graph["volumes"]["core_data"] = {}
        graph["services"]["core"]["volumes"] = [{"type": "volume", "source": "core_data", "target": "/data"}]
        module.validate_compose(graph, self.root, "default")

    def test_demo_hardened_service_accepted(self):
        graph = copy.deepcopy(self.graph)
        graph["services"]["demo"] = {"volumes": [], "read_only": True, "cap_drop": ["ALL"],
                                      "security_opt": ["no-new-privileges:true"], "ports": []}
        module.validate_compose(graph, self.root, "demo")


if __name__ == "__main__":
    unittest.main()
