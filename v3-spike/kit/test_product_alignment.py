"""Negative mutation tests for BOM/Compose and provenance alignment; synthetic only."""
import json
import tempfile
import unittest
from pathlib import Path

import yaml
from test_product_preflight import valid
from verify_product_compose import verify as verify_compose, verify_draft_volumes, DRAFT_VOLUMES
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
    def test_allow_no_new_privileges_hardening(self):
        self.compose["services"]["core"]["security_opt"] = ["no-new-privileges:true"]
        b,c,_ = self.files()
        self.assertTrue(verify_compose(b,c))
    def test_reject_unapproved_security_opt(self):
        self.compose["services"]["core"]["security_opt"] = ["seccomp:unconfined"]
        b,c,_ = self.files()
        with self.assertRaisesRegex(ValueError, "host capability"):
            verify_compose(b,c)
    def test_allow_container_only_protected_port(self):
        self.compose["services"]["core"]["ports"] = [7770, "7777"]
        b,c,_ = self.files()
        self.assertTrue(verify_compose(b,c))
    def test_reject_explicit_published_7790(self):
        self.compose["services"]["core"]["ports"] = ["7790:8080"]
        b,c,_ = self.files()
        with self.assertRaisesRegex(ValueError, "protected port"):
            verify_compose(b,c)
    def _profile_fixture(self):
        self.bom["services"]["demo"] = {
            "image": "example.org/v3/demo@sha256:" + "b" * 64,
            "profile": "demo", "secrets": [], "migration": False}
        self.compose["services"]["demo"] = {
            "image": self.bom["services"]["demo"]["image"], "profiles": ["demo"]}
        return self.files()

    def test_normalized_default_excludes_demo(self):
        b, c, _ = self._profile_fixture()
        effective = {"services": {k: v for k, v in self.compose["services"].items()
                                   if k != "demo"}}
        n = self.root / "normalized.json"
        n.write_text(json.dumps(effective))
        self.assertTrue(verify_compose(b, c, n))

    def test_normalized_demo_includes_demo(self):
        b, c, _ = self._profile_fixture()
        n = self.root / "normalized.json"
        n.write_text(json.dumps({"services": self.compose["services"]}))
        self.assertTrue(verify_compose(b, c, n))

    def test_normalized_rejects_missing_required_service(self):
        b, c, _ = self._profile_fixture()
        effective = {"services": {k: v for k, v in self.compose["services"].items()
                                   if k not in ("demo", "core")}}
        n = self.root / "normalized.json"
        n.write_text(json.dumps(effective))
        with self.assertRaisesRegex(ValueError, "normalized Compose service set mismatch"):
            verify_compose(b, c, n)
    def _effective_volume_fixture(self, effective_name="aiops-v3_data"):
        self.compose["volumes"] = {"data": {}}
        self.compose["services"]["core"]["volumes"] = ["data:/data"]
        b, c, _ = self.files()
        effective = {"services": json.loads(json.dumps(self.compose["services"])),
                     "volumes": {"data": {"name": effective_name}}}
        effective["services"]["core"]["volumes"] = [
            {"type": "volume", "source": effective_name, "target": "/data"}]
        n = self.root / "normalized.json"
        n.write_text(json.dumps(effective))
        return b, c, n, effective

    def test_normalized_accepts_effective_project_volume_name(self):
        b, c, n, _ = self._effective_volume_fixture()
        self.assertTrue(verify_compose(b, c, n))

    def test_normalized_rejects_undeclared_effective_volume_source(self):
        b, c, n, effective = self._effective_volume_fixture()
        effective["services"]["core"]["volumes"][0]["source"] = "external_secret"
        n.write_text(json.dumps(effective))
        with self.assertRaisesRegex(ValueError, "undeclared long-form volume source"):
            verify_compose(b, c, n)

    def test_normalized_rejects_duplicate_effective_volume_alias(self):
        b, c, n, effective = self._effective_volume_fixture()
        self.compose["volumes"]["other"] = {}
        c.write_text(yaml.safe_dump(self.compose))
        effective["volumes"]["other"] = {"name": "aiops-v3_data"}
        n.write_text(json.dumps(effective))
        with self.assertRaisesRegex(ValueError, "duplicate effective volume names"):
            verify_compose(b, c, n)

    def test_normalized_rejects_raw_root_bind_driver_options(self):
        b, c, n, _ = self._effective_volume_fixture()
        self.compose["volumes"]["data"] = {"driver_opts": {"type": "none", "o": "bind", "device": "/"}}
        c.write_text(yaml.safe_dump(self.compose))
        with self.assertRaisesRegex(ValueError, "untrusted named volume"):
            verify_compose(b, c, n)

    def test_normalized_rejects_raw_external_volume(self):
        b, c, n, _ = self._effective_volume_fixture()
        self.compose["volumes"]["data"] = {"external": True}
        c.write_text(yaml.safe_dump(self.compose))
        with self.assertRaisesRegex(ValueError, "untrusted named volume"):
            verify_compose(b, c, n)

    def test_normalized_rejects_effective_bind_driver_options(self):
        b, c, n, effective = self._effective_volume_fixture()
        effective["volumes"]["data"]["driver_opts"] = {"type": "none", "o": "bind", "device": "/etc"}
        n.write_text(json.dumps(effective))
        with self.assertRaisesRegex(ValueError, "untrusted normalized named volume"):
            verify_compose(b, c, n)

    def test_normalized_rejects_effective_external_volume(self):
        b, c, n, effective = self._effective_volume_fixture()
        effective["volumes"]["data"]["external"] = True
        n.write_text(json.dumps(effective))
        with self.assertRaisesRegex(ValueError, "untrusted normalized named volume"):
            verify_compose(b, c, n)

    def test_normalized_allows_effective_local_driver(self):
        b, c, n, effective = self._effective_volume_fixture()
        effective["volumes"]["data"]["driver"] = "local"
        n.write_text(json.dumps(effective))
        self.assertTrue(verify_compose(b, c, n))

    def test_reject_old_images_only_bom_schema(self):
        self.bom = {"images": {"core": "example.org/core@sha256:" + "a"*64}}
        b,c,p = self.files()
        with self.assertRaises(ValueError):
            verify_compose(b,c)
        with self.assertRaises(ValueError):
            verify_provenance(b,p)


class DraftVolumeTests(unittest.TestCase):
    def setUp(self):
        self.doc = {"name": "aiops-v3", "services": {"gamma": {}}, "volumes": {}}
        for service, (key, target) in DRAFT_VOLUMES.items():
            self.doc["volumes"][key] = {"name": "aiops-v3_" + key}
            self.doc["services"][service] = {"volumes": [
                {"type": "volume", "source": key, "target": target, "volume": {}}]}
    def check(self):
        verify_draft_volumes(self.doc, normalized=True)
    def mount(self):
        return self.doc["services"]["core"]["volumes"][0]
    def test_default_logical(self):
        self.check()
    def test_demo_logical(self):
        self.doc["services"]["demo"] = {}
        self.check()
    def test_default_effective(self):
        self.mount()["source"] = "aiops-v3_core_data"
        self.check()
    def test_demo_effective(self):
        self.doc["services"]["demo"] = {}
        self.mount()["source"] = "aiops-v3_core_data"
        self.check()
    def test_bind(self):
        self.mount()["type"] = "bind"
        with self.assertRaises(ValueError): self.check()
    def test_unknown(self):
        self.mount()["source"] = "unknown"
        with self.assertRaises(ValueError): self.check()
    def test_other_owner(self):
        self.mount()["source"] = "evidence_data"
        with self.assertRaises(ValueError): self.check()
    def test_external(self):
        self.doc["volumes"]["core_data"]["external"] = True
        with self.assertRaises(ValueError): self.check()
    def test_driver_opts(self):
        self.doc["volumes"]["core_data"]["driver_opts"] = {"device": "/"}
        with self.assertRaises(ValueError): self.check()
    def test_wrong_effective_name(self):
        self.doc["volumes"]["core_data"]["name"] = "foreign"
        with self.assertRaises(ValueError): self.check()
    def test_wrong_target(self):
        self.mount()["target"] = "/wrong"
        with self.assertRaises(ValueError): self.check()
    def test_extra_mount(self):
        self.doc["services"]["core"]["volumes"].append(dict(self.mount()))
        with self.assertRaises(ValueError): self.check()
    def test_subpath(self):
        self.mount()["volume"]["subpath"] = "other"
        with self.assertRaises(ValueError): self.check()
    def test_missing_mount(self):
        self.doc["services"]["core"]["volumes"] = []
        with self.assertRaises(ValueError): self.check()

if __name__ == "__main__":
    unittest.main()
