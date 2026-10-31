import os
import sys
import pathlib
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "app"))
from intelligence import main as module


class ModelDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.base = module.BASE
        self.model = module.MODEL
        self.key = module.KEY
        module.BASE = "http://10.79.94.31:8000/v1"
        module.MODEL = ""
        module.KEY = ""

    def tearDown(self):
        module.BASE = self.base
        module.MODEL = self.model
        module.KEY = self.key

    def response(self, ids):
        response = Mock()
        response.json.return_value = {"data": [{"id": item} for item in ids]}
        response.raise_for_status.return_value = None
        return response

    @patch.object(module.requests, "get")
    def test_discovers_unique_nemotron_120b_without_auth(self, get):
        get.return_value = self.response([
            "nvidia/nemotron-120b",
            "nvidia/other-model",
        ])
        selected = module.resolve_model_id()
        self.assertEqual(selected, "nvidia/nemotron-120b")
        args, kwargs = get.call_args
        self.assertEqual(args[0], "http://10.79.94.31:8000/v1/models")
        self.assertNotIn("Authorization", kwargs.get("headers", {}))
        self.assertEqual(module.MODEL, selected)

    @patch.object(module.requests, "get")
    def test_single_available_model_is_selected(self, get):
        get.return_value = self.response(["nvidia/custom-deployment"])
        self.assertEqual(module.resolve_model_id(), "nvidia/custom-deployment")

    @patch.object(module.requests, "get")
    def test_ambiguous_models_fail_closed(self, get):
        get.return_value = self.response(["model-a", "model-b"])
        with self.assertRaises(module.HTTPException) as caught:
            module.resolve_model_id()
        self.assertEqual(caught.exception.status_code, 503)
        self.assertEqual(caught.exception.detail, "llm_model_selection_required")
        self.assertEqual(module.MODEL, "")

    @patch.object(module.requests, "get")
    def test_explicit_model_skips_discovery(self, get):
        module.MODEL = "nvidia/nemotron-120b"
        self.assertEqual(module.resolve_model_id(), module.MODEL)
        get.assert_not_called()


if __name__ == "__main__":
    unittest.main()
