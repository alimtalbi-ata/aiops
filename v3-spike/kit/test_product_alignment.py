"""Negative mutation tests for BOM/Compose and provenance alignment; synthetic only."""
import json
import tempfile
import unittest
from pathlib import Path

import yaml
from test_product_preflight import valid
from verify_product_compose import verify as verify_compose
from verify_product_provenance import verify as verify_provenance

class ProductAlignmentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bom = valid()
        self.compose = {"services": {name: {"image": entry["image"]}
                     for name, entry in self.bom["services"].items()}}
        self.provenance = {"images": {name: {"image": entry["image"], "license": "TEST-ONLY",
                              "source": "synthetic", "registry_receipt": "synthetic"}
                       for name, entry in self.bom["services"].items()}}
    def files(self):
        b, c, p = (self.root / n for n in ("bom.json", "docker-compose.yml", "provenance.json"))
        b.write_text(json.dumps(self.bom))
        c.write_text(yaml.safe_dump(self.compose))
        p.write_text(json.dumps(self.provenance))
        return b, c, p
    def test_synthetic_alignment_static_only(self):
        b,c,p = self.files()
        self.assertTrue(verify_compose(b,c))
        self.assertTrue(verify_provenance(b,p))
    def test_reject_compose_image_swapped_between_services(self):
        self.compose["services"]["core"]["image"] = self.bom["services"]["gamma"]["image"]
        b,c,_ = self.files()
        with self.assertRaisesRegex(ValueError, "image mismatch"):
            verify_compose(b,c)
    def test_reject_compose_missing_service(self):
        del self.compose["services"]["evidence"]
        b,c,_ = self.files()
        with self.assertRaisesRegex(ValueError, "service set"):
            verify_compose(b,c)
    def test_reject_required_hidden_profile(self):
        self.compose["services"]["core"]["profiles"] = ["demo"]
        b,c,_ = self.files()
        with self.assertRaisesRegex(ValueError, "hidden"):
            verify_compose(b,c)
    def test_reject_provenance_missing_service(self):
        del self.provenance["images"]["worker"]
        b,_,p = self.files()
        with self.assertRaisesRegex(ValueError, "service set"):
            verify_provenance(b,p)
    def test_reject_provenance_false_attestation(self):
        self.provenance["independently_verified"] = True
        b,_,p = self.files()
        with self.assertRaisesRegex(ValueError, "untrusted attestation"):
            verify_provenance(b,p)
    def test_reject_provenance_empty_license(self):
        self.provenance["images"]["core"]["license"] = " "
        b,_,p = self.files()
        with self.assertRaisesRegex(ValueError, "license"):
            verify_provenance(b,p)
    def test_reject_forged_true_attestation(self):
        self.provenance["independently_verified"] = True
        b,_,p = self.files()
        with self.assertRaisesRegex(ValueError, "untrusted attestation"):
            verify_provenance(b,p)
    def test_reject_privileged(self):
        self.compose["services"]["core"]["privileged"] = True
        b,c,_ = self.files()
        with self.assertRaisesRegex(ValueError, "privileged"):
            verify_compose(b,c)
    def test_reject_host_network(self):
        self.compose["services"]["core"]["network_mode"] = "host"
        b,c,_ = self.files()
        with self.assertRaisesRegex(ValueError, "host namespace"):
            verify_compose(b,c)
    def test_reject_host_root_mount(self):
        self.compose["services"]["core"]["volumes"] = ["/:/host:rw"]
        b,c,_ = self.files()
        with self.assertRaisesRegex(ValueError, "bind mount"):
            verify_compose(b,c)
    def test_reject_protected_port(self):
        self.compose["services"]["core"]["ports"] = ["7770:8080"]
        b,c,_ = self.files()
        with self.assertRaisesRegex(ValueError, "protected port"):
            verify_compose(b,c)
    def test_reject_interpolated_host_root(self):
        self.compose["services"]["core"]["volumes"] = ["${HOST_ROOT}:/host:rw"]
        b,c,_ = self.files()
        with self.assertRaisesRegex(ValueError, "interpolation"):
            verify_compose(b,c)
    def test_reject_interpolated_protected_port(self):
        self.compose["services"]["core"]["ports"] = ["${HOST_PORT}:8080"]
        b,c,_ = self.files()
        with self.assertRaisesRegex(ValueError, "interpolation"):
            verify_compose(b,c)
    def test_reject_container_network_namespace(self):
        self.compose["services"]["core"]["network_mode"] = "container:other"
        b,c,_ = self.files()
        with self.assertRaisesRegex(ValueError, "host namespace"):
            verify_compose(b,c)
    def test_reject_service_pid_namespace(self):
        self.compose["services"]["core"]["pid"] = "service:other"
        b,c,_ = self.files()
        with self.assertRaisesRegex(ValueError, "host namespace"):
            verify_compose(b,c)
    def test_reject_relative_bind(self):
        self.compose["volumes"] = {"subdir": {}}
        self.compose["services"]["core"]["volumes"] = ["subdir:/host:rw"]
        b,c,_ = self.files()
        self.assertTrue(verify_compose(b,c))  # named volume, not bind
        self.compose["services"]["core"]["volumes"] = ["../secret:/host:rw"]
        b,c,_ = self.files()
        with self.assertRaisesRegex(ValueError, "bind mount"):
            verify_compose(b,c)
    def test_reject_volumes_from_service(self):
        self.compose["services"]["core"]["volumes_from"] = ["other:rw"]
        b,c,_ = self.files()
        with self.assertRaisesRegex(ValueError, "volumes_from"):
            verify_compose(b,c)
    def test_reject_volumes_from_external_container(self):
        self.compose["services"]["core"]["volumes_from"] = ["container:external:rw"]
        b,c,_ = self.files()
        with self.assertRaisesRegex(ValueError, "volumes_from"):
            verify_compose(b,c)
    def test_reject_transitive_extends(self):
        self.compose["services"]["core"]["extends"] = {"file": "../external.yml", "service": "host"}
        b,c,_ = self.files()
        with self.assertRaisesRegex(ValueError, "extends"):
            verify_compose(b,c)
    def test_reject_transitive_include(self):
        self.compose["include"] = ["../external.yml"]
        b,c,_ = self.files()
        with self.assertRaisesRegex(ValueError, "include"):
            verify_compose(b,c)
    def test_reject_host_userns(self):
        self.compose["services"]["core"]["userns_mode"] = "host"
        b,c,_ = self.files()
        with self.assertRaisesRegex(ValueError, "host namespace"):
            verify_compose(b,c)
    def test_reject_host_cgroup(self):
        self.compose["services"]["core"]["cgroup"] = "host"
        b,c,_ = self.files()
        with self.assertRaisesRegex(ValueError, "host namespace"):
            verify_compose(b,c)
    def test_reject_host_uts(self):
        self.compose["services"]["core"]["uts"] = "host"
        b,c,_ = self.files()
        with self.assertRaisesRegex(ValueError, "host namespace"):
            verify_compose(b,c)
    def test_reject_named_volume_host_root_driver(self):
        self.compose["services"]["core"]["volumes"] = ["data:/data"]
        self.compose["volumes"] = {"data": {"driver": "local", "driver_opts": {"type": "none", "o": "bind", "device": "/"}}}
        b,c,_ = self.files()
        with self.assertRaisesRegex(ValueError, "named volume"):
            verify_compose(b,c)
    def test_reject_named_volume_external(self):
        self.compose["services"]["core"]["volumes"] = ["data:/data"]
        self.compose["volumes"] = {"data": {"external": True}}
        b,c,_ = self.files()
        with self.assertRaisesRegex(ValueError, "named volume"):
            verify_compose(b,c)
    def test_reject_long_form_host_root_volume(self):
        for source in ("/", "/etc", "../secret", "./data"):
            with self.subTest(source=source):
                self.compose["services"]["core"]["volumes"] = [
                    {"type": "volume", "source": source, "target": "/host"}]
                b,c,_ = self.files()
                with self.assertRaisesRegex(ValueError, "long-form volume source"):
                    verify_compose(b,c)
    def test_reject_long_form_undeclared_volume(self):
        self.compose["services"]["core"]["volumes"] = [
            {"type": "volume", "source": "undeclared", "target": "/data"}]
        b,c,_ = self.files()
        with self.assertRaisesRegex(ValueError, "undeclared long-form volume source"):
            verify_compose(b,c)
    def test_allow_declared_long_form_volume(self):
        self.compose["volumes"] = {"data": {}}
        self.compose["services"]["core"]["volumes"] = [
            {"type": "volume", "source": "data", "target": "/data"}]
        b,c,_ = self.files()
        self.assertTrue(verify_compose(b,c))
    def test_reject_undeclared_short_form_volume(self):
        self.compose["services"]["core"]["volumes"] = ["unknown:/data"]
        b,c,_ = self.files()
        with self.assertRaisesRegex(ValueError, "undeclared short-form volume"):
            verify_compose(b,c)
    def test_allow_declared_short_form_volume(self):
        self.compose["volumes"] = {"data": {}}
        self.compose["services"]["core"]["volumes"] = ["data:/data"]
        b,c,_ = self.files()
        self.assertTrue(verify_compose(b,c))
    def test_reject_old_images_only_bom_schema(self):
        self.bom = {"images": {"core": "example.org/core@sha256:" + "a"*64}}
        b,c,p = self.files()
        with self.assertRaises(ValueError):
            verify_compose(b,c)
        with self.assertRaises(ValueError):
            verify_provenance(b,p)

if __name__ == "__main__":
    unittest.main()
