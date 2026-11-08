"""#460: independently exercise the immutable #453 synthetic contract.

Run: python3 -m unittest discover -s tests -p 'test_fs147_twin_460_*.py' -v
Requires the Git object below (fetch its source branch if missing). No network
or application service is used by these tests. No production/E2E claim.
"""
import copy
import pathlib
import subprocess
import sys
import types
import unittest
from unittest.mock import patch


SOURCE_SHA = "d99f552a2e48b9dcdd0bbda585e1d1339c670576"
ROOT = pathlib.Path(__file__).resolve().parents[1]


def load_contract(name):
    source = subprocess.check_output(
        ["git", "show", f"{SOURCE_SHA}:tests/{name}.py"], cwd=ROOT
    )
    module = types.ModuleType(name)
    exec(compile(source, f"{SOURCE_SHA}:tests/{name}.py", "exec"), module.__dict__)
    return module


class ReplayIsolation460(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.boundary = load_contract("test_fs147_twin_adapter_boundary_contract")
        with patch.dict(sys.modules, {
            "test_fs147_twin_adapter_boundary_contract": cls.boundary
        }):
            cls.ingress = load_contract("test_fs147_twin_nested_provenance_contract")

    def test_returned_result_cannot_poison_next_replay(self):
        first = self.boundary.qualify_pair(self.boundary.LAB, self.boundary.SAN)
        first["live_fs147"] = "forged"
        self.assertEqual(self.boundary.qualify_pair(
            self.boundary.LAB, self.boundary.SAN)["live_fs147"], "UNKNOWN")

    def test_foreign_fixture_uri_fails_closed_in_both_directions(self):
        # Regression discovered in #460. Keep failures visible until the owner
        # of #453 corrects its validator; do not weaken or mark expectedFailure.
        for own, foreign in ((self.boundary.LAB, self.boundary.SAN),
                             (self.boundary.SAN, self.boundary.LAB)):
            with self.subTest(graph=own["graph"]):
                event = copy.deepcopy(own)
                event["metadata"] = {"uri": "fixture://foreign/" + foreign["run_id"]}
                with self.assertRaises(ValueError):
                    self.ingress.reject_foreign_provenance(event, foreign)


if __name__ == "__main__":
    unittest.main()
