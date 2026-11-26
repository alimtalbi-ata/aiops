"""Synthetic rootless preflight regressions; no Docker invocation."""
import importlib.util
import copy
import json
import tempfile
from pathlib import Path
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

spec = importlib.util.spec_from_file_location("rootless_preflight", Path(__file__).with_name("rootless_preflight.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class RootlessPreflightTests(unittest.TestCase):
    def setUp(self):
        self.root = Path("/srv/aiops-v3")
        self.info = {"SecurityOptions": ["name=seccomp", "name=rootless"],
                     "DockerRootDir": "/srv/aiops-v3/docker-data"}
        self.env = {k + "_IMAGE": "registry.example/" + k.lower() + "@sha256:" + ("%064x" % (i + 1)) for i, k in enumerate(module.IMAGE_KEYS)}
        self.env["DEMO_IMAGE"] = "registry.example/demo@sha256:" + ("f" * 64)
        self.graph = {"services": {k.lower(): {"volumes": [], "read_only": True, "cap_drop": ["ALL"],
                          "security_opt": ["no-new-privileges:true"], "ports": [], "image": self.env[k + "_IMAGE"]} for k in module.IMAGE_KEYS}, "volumes": {}}
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

    def test_source_daemon_preflight_strict_confinement(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            root = base / "install"
            root.mkdir()
            inside = root / "docker-data"
            inside.mkdir()
            outside = base / "outside"
            outside.mkdir()
            alias = root / "alias"
            alias.symlink_to(outside, target_is_directory=True)
            internal_alias = root / "internal-alias"
            internal_alias.symlink_to(inside, target_is_directory=True)
            host = "unix:///run/user/1001/docker.sock"
            env = {"DOCKER_HOST": host}
            for data, accepted in ((inside, True), (root, False), (outside, False),
                                   (alias, False), (internal_alias, False), (root / "missing", False)):
                with self.subTest(data=data):
                    info = {"SecurityOptions": ["name=rootless"], "DockerRootDir": str(data)}
                    command = Mock(return_value=SimpleNamespace(stdout=json.dumps(info)))
                    if accepted:
                        self.assertEqual(module.source_daemon_preflight(root, env, command, uid=1001)["status"], "PASS")
                    else:
                        with self.assertRaises(ValueError):
                            module.source_daemon_preflight(root, env, command, uid=1001)
                    command.assert_called_once_with(["docker", "info", "--format", "{{json .}}"],
                                                    capture_output=True, text=True, check=True, env=env)
            for bad_env, uid in (({}, 1001), ({"DOCKER_HOST": "unix:///var/run/docker.sock"}, 1001),
                                 (dict(env, DOCKER_CONTEXT="other"), 1001), (env, 0)):
                with self.subTest(env=bad_env, uid=uid):
                    command = Mock()
                    with self.assertRaises(ValueError):
                        module.source_daemon_preflight(root, bad_env, command, uid=uid)
                    command.assert_not_called()

    def test_bind_escape_rejected(self):
        self.graph["services"]["core"]["volumes"] = [{"type": "bind", "source": "/etc", "target": "/etc"}]
        with self.assertRaisesRegex(ValueError, "escapes"):
            module.validate_compose(self.graph, self.root, "default", self.env)

    def test_external_volume_rejected(self):
        self.graph["volumes"] = {"data": {"external": True}}
        with self.assertRaisesRegex(ValueError, "external"):
            module.validate_compose(self.graph, self.root, "default", self.env)

    def test_default_service_graph_accepted(self):
        module.validate_compose(self.graph, self.root, "default", self.env)

    def test_demo_requires_demo_service(self):
        with self.assertRaisesRegex(ValueError, "service set"):
            module.validate_compose(self.graph, self.root, "demo", self.env)

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
                    module.validate_compose(graph, self.root, "default", self.env)

    def test_undeclared_named_volume_rejected(self):
        graph = copy.deepcopy(self.graph)
        graph["services"]["core"]["volumes"] = [{"type": "volume", "source": "missing", "target": "/data"}]
        with self.assertRaisesRegex(ValueError, "undeclared"):
            module.validate_compose(graph, self.root, "default", self.env)

    def test_read_write_bind_rejected(self):
        graph = copy.deepcopy(self.graph)
        graph["services"]["core"]["volumes"] = [{"type": "bind", "source": "/srv/aiops-v3/data", "target": "/data"}]
        with self.assertRaisesRegex(ValueError, "read-only"):
            module.validate_compose(graph, self.root, "default", self.env)

    def test_non_gamma_published_port_rejected(self):
        graph = copy.deepcopy(self.graph)
        graph["services"]["core"]["ports"] = [{"host_ip": "127.0.0.1", "published": "19000", "target": 9000}]
        with self.assertRaisesRegex(ValueError, "only GAMMA"):
            module.validate_compose(graph, self.root, "default", self.env)

    def test_gamma_public_port_rejected(self):
        graph = copy.deepcopy(self.graph)
        graph["services"]["gamma"]["ports"][0]["host_ip"] = "0.0.0.0"
        with self.assertRaisesRegex(ValueError, "loopback-only"):
            module.validate_compose(graph, self.root, "default", self.env)

    def test_declared_named_volume_accepted(self):
        graph = copy.deepcopy(self.graph)
        graph["volumes"]["core_data"] = {}
        graph["services"]["core"]["volumes"] = [{"type": "volume", "source": "core_data", "target": "/data"}]
        module.validate_compose(graph, self.root, "default", self.env)

    def test_demo_hardened_service_accepted(self):
        graph = copy.deepcopy(self.graph)
        graph["services"]["demo"] = {"volumes": [], "read_only": True, "cap_drop": ["ALL"],
                                      "security_opt": ["no-new-privileges:true"], "ports": [], "image": self.env["DEMO_IMAGE"]}
        module.validate_compose(graph, self.root, "demo", self.env)


    def test_normalized_image_mutations_rejected(self):
        for mutation in ("tag", "different_digest", "missing", "empty"):
            with self.subTest(mutation=mutation):
                graph = copy.deepcopy(self.graph)
                if mutation == "tag":
                    graph["services"]["core"]["image"] = "registry.example/core:latest"
                elif mutation == "different_digest":
                    graph["services"]["core"]["image"] = self.env["WORKER_IMAGE"]
                elif mutation == "missing":
                    del graph["services"]["core"]["image"]
                else:
                    graph["services"]["core"]["image"] = ""
                with self.assertRaisesRegex(ValueError, "image"):
                    module.validate_compose(graph, self.root, "default", self.env)

    def test_demo_placeholder_and_binding_rejected(self):
        graph = copy.deepcopy(self.graph)
        graph["services"]["demo"] = {"volumes": [], "read_only": True, "cap_drop": ["ALL"],
                                     "security_opt": ["no-new-privileges:true"], "ports": [],
                                     "image": self.env["DEMO_IMAGE"]}
        module.validate_compose(graph, self.root, "demo", self.env)
        graph["services"]["demo"]["image"] = "registry.invalid/disabled-demo@sha256:" + ("0" * 64)
        with self.assertRaisesRegex(ValueError, "image"):
            module.validate_compose(graph, self.root, "demo", self.env)

    def test_active_placeholder_rejected_even_when_bound(self):
        for image in ("registry.invalid/disabled-demo@sha256:" + "f" * 64,
                      "registry.example/demo@sha256:" + "0" * 64):
            with self.subTest(image=image):
                env = dict(self.env, DEMO_IMAGE=image)
                graph = copy.deepcopy(self.graph)
                graph["services"]["demo"] = dict(graph["services"]["core"], image=image)
                with self.assertRaisesRegex(ValueError, "references missing"):
                    module.validate_compose(graph, self.root, "demo", env)
                module.validate_compose(self.graph, self.root, "default", env)

    def test_security_option_overrides_rejected(self):
        for option in ("seccomp=unconfined", "apparmor:unconfined", "label=disable", "no-new-privileges:false"):
            with self.subTest(option=option):
                graph = copy.deepcopy(self.graph)
                graph["services"]["core"]["security_opt"].append(option)
                with self.assertRaisesRegex(ValueError, "unsupported security_opt"):
                    module.validate_compose(graph, self.root, "default", self.env)

    def test_namespace_and_privilege_mutations_rejected(self):
        mutations = {
            "network_mode": ("service:core", "container:other", "host"),
            "pid": ("host", "service:core"),
            "ipc": ("host", "shareable"),
            "devices": (["/dev/kvm:/dev/kvm"],),
            "volumes_from": (["core"],),
            "cap_add": (["SYS_ADMIN"],),
            "device_cgroup_rules": (["c 1:3 rwm"],),
            "userns_mode": ("host",),
        }
        for key, values in mutations.items():
            for value in values:
                with self.subTest(key=key, value=value):
                    graph = copy.deepcopy(self.graph)
                    graph["services"]["core"][key] = value
                    expected = "unsafe container privileges" if key == "network_mode" and value == "host" else "forbidden isolation setting: " + key
                    with self.assertRaisesRegex(ValueError, expected):
                        module.validate_compose(graph, self.root, "default", self.env)

    def test_root_user_mutations_rejected(self):
        for value in ("root", "0", "0:0", "root:root", "0:root", "root:0", "1000:0", "1000:root"):
            with self.subTest(user=value):
                graph = copy.deepcopy(self.graph)
                graph["services"]["core"]["user"] = value
                with self.assertRaisesRegex(ValueError, "user"):
                    module.validate_compose(graph, self.root, "default", self.env)

    def test_nonroot_numeric_user_accepted(self):
        graph = copy.deepcopy(self.graph)
        graph["services"]["core"]["user"] = "10001:10001"
        module.validate_compose(graph, self.root, "default", self.env)


if __name__ == "__main__":
    unittest.main()
