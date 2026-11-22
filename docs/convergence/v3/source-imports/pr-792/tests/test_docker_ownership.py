import importlib.util
import json
import pathlib
import unittest
from unittest.mock import patch

ROOT=pathlib.Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location("resource_fence",ROOT/"deploy"/"check-docker-ownership.py")
MODULE=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
PROJECT="aiops2-rebuild"

class OwnershipFenceTests(unittest.TestCase):
    def test_identifies_each_resource_and_rejects_unprefixed(self):
        spec={"services":{"core":{"container_name":PROJECT+"-core"}},
              "networks":{"control":{"name":PROJECT+"-control"}},
              "volumes":{"data":{"name":PROJECT+"-data"}}}
        resources=MODULE.inspect_resources(spec)
        self.assertEqual(set(resources),{("container",PROJECT+"-core"),("network",PROJECT+"-control"),("volume",PROJECT+"-data")})

    def test_foreign_container_is_blocked(self):
        original={"Config":{"Labels":{"com.docker.compose.project":"other"}}}
        with patch.object(MODULE,"docker",return_value=(0,json.dumps([original]),'' )):
            error=MODULE.check_resource("container",PROJECT+"-core",PROJECT)
        self.assertEqual(error,"container_owned_by_other_project:"+PROJECT+"-core")

    def test_foreign_volume_is_blocked_even_if_name_matches(self):
        original={"Labels":{"com.docker.compose.project":"aiops2"}}
        with patch.object(MODULE,"docker",return_value=(0,json.dumps([original]),"")):
            error=MODULE.check_resource("volume",PROJECT+"-data",PROJECT)
        self.assertEqual(error,"volume_owned_by_other_project:"+PROJECT+"-data")

    def test_owned_resources_pass(self):
        for kind in ("container","network","volume"):
            data={"Config":{"Labels":{"com.docker.compose.project":PROJECT}}} if kind=="container" else {"Labels":{"com.docker.compose.project":PROJECT}}
            with self.subTest(kind=kind),patch.object(MODULE,"docker",return_value=(0,json.dumps([data]),'' )):
                self.assertIsNone(MODULE.check_resource(kind,PROJECT+"-x",PROJECT))

    def test_missing_resources_are_safe_to_create(self):
        with patch.object(MODULE,"docker",return_value=(1,"","Error: No such object: missing")):
            self.assertIsNone(MODULE.check_resource("container",PROJECT+"-core",PROJECT))

    def test_corrupt_existing_inspect_fails_closed(self):
        with patch.object(MODULE,"docker",return_value=(0,"not-json","")):
            self.assertEqual(MODULE.check_resource("volume",PROJECT+"-data",PROJECT),
                             "volume_inspect_unparseable:"+PROJECT+"-data")


    def test_docker_unavailable_fails_closed(self):
        with patch.object(MODULE,"docker",return_value=(1,"","Cannot connect to the Docker daemon")):
            error=MODULE.check_resource("container",PROJECT+"-core",PROJECT)
        self.assertEqual(error,"container_inspect_unavailable:"+PROJECT+"-core")

    def test_permission_denied_volume_fails_closed(self):
        with patch.object(MODULE,"docker",return_value=(1,"","permission denied")):
            error=MODULE.check_resource("volume",PROJECT+"-data",PROJECT)
        self.assertEqual(error,"volume_inspect_unavailable:"+PROJECT+"-data")

    def test_network_missing_and_network_error_are_distinct(self):
        self.assertTrue(MODULE.is_missing("network","Error: network xyz not found"))
        self.assertFalse(MODULE.is_missing("network","Cannot connect to the Docker daemon"))

if __name__=="__main__":
    unittest.main()
