import unittest
from unittest.mock import patch

from scripts.qualify_nim_runtime import MARKER, qualify, safe_base_url


class NimRuntimeQualificationTests(unittest.TestCase):
    def test_normalizes_v1_base_url_without_credentials(self):
        self.assertEqual(safe_base_url("https://nim.example:8000/v1/"), "https://nim.example:8000")

    def test_rejects_credentials_embedded_in_url(self):
        with self.assertRaises(ValueError):
            safe_base_url("https://user:secret@nim.example:8000")

    @patch("scripts.qualify_nim_runtime.request_json")
    def test_pass_requires_exact_model_and_probe_completion(self, request):
        request.side_effect = [
            ({"data": [{"id": "nvidia/nemotron-120b"}]}, 12.5, 200),
            ({
                "choices": [{"message": {"content": MARKER}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 18, "completion_tokens": 4, "total_tokens": 22},
            }, 85.2, 200),
        ]
        result = qualify("https://nim.example", "nvidia/nemotron-120b", 30)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["provider"], "nim")
        self.assertEqual(result["usage"]["total_tokens"], 22)

    @patch("scripts.qualify_nim_runtime.request_json")
    def test_unknown_model_fails_before_completion(self, request):
        request.return_value = ({"data": [{"id": "another-model"}]}, 10, 200)
        result = qualify("https://nim.example", "nvidia/nemotron-120b", 30)
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(result["models_api"]["status"], "MODEL_NOT_LISTED")
        request.assert_called_once()

    @patch("scripts.qualify_nim_runtime.request_json")
    def test_completion_without_probe_marker_fails(self, request):
        request.side_effect = [
            ({"data": [{"id": "nemotron"}]}, 10, 200),
            ({"choices": [{"message": {"content": "I am available."}}]}, 20, 200),
        ]
        result = qualify("https://nim.example", "nemotron", 30)
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(result["completion_api"]["status"], "UNEXPECTED_MODEL_RESPONSE")

    @patch("scripts.qualify_nim_runtime.request_json")
    def test_auto_selects_unique_nemotron_120b_model(self, request):
        request.side_effect = [
            ({"data": [{"id": "nvidia/nemotron-120b"}]}, 10, 200),
            ({"choices": [{"message": {"content": MARKER}}]}, 20, 200),
        ]
        result = qualify("https://nim.example", "", 30)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["model"], "nvidia/nemotron-120b")

    @patch("scripts.qualify_nim_runtime.request_json")
    def test_multiple_unmatched_models_require_explicit_selection(self, request):
        request.return_value = ({"data": [{"id": "model-a"}, {"id": "model-b"}]}, 10, 200)
        result = qualify("https://nim.example", "", 30)
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(result["models_api"]["status"], "MODEL_SELECTION_REQUIRED")
        self.assertEqual(len(result["models_api"]["available_model_ids"]), 2)
        request.assert_called_once()


if __name__ == "__main__":
    unittest.main()
