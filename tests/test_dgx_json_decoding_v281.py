"""V2.8.1: DGX JSON framing never bypasses strict contract validation."""
import importlib.util
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))
SPEC = importlib.util.spec_from_file_location("aiops_intelligence_dgx_v281", ROOT / "app" / "intelligence" / "main.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class DgxJsonDecodingTests(unittest.TestCase):
    def test_plain_json_object(self):
        self.assertEqual(MODULE.decode_model_json(' {"severity":"P1"} '), {"severity": "P1"})

    def test_complete_json_markdown_fence(self):
        self.assertEqual(MODULE.decode_model_json('```json\n{"severity":"P2"}\n```'), {"severity": "P2})

    def test_case_insensitive_json_fence(self):
        self.assertEqual(MODULE.decode_model_json('```JSON\n{"ok":true}\n```'), {"ok": True})

    def test_rejects_truncation(self):
        with self.assertRaises(ValueError):
            MODULE.decode_model_json('```json\n{"severity":"P1"}')

    def test_rejects_prose_and_multiple_objects(self):
        for value in ('Here is JSON: {"ok":true}', '{"a":1} {"b":2}', '```python\n{"x":1}\n```'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                MODULE.decode_model_json(value)

    def test_rejects_array_and_null(self):
        for value in ('[]', 'null', '42'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                MODULE.decode_model_json(value)

    def test_schema_remains_strict(self):
        with self.assertRaises(Exception):
            MODULE.Analyst.model_validate(MODULE.decode_model_json('```json\n{"severity":"Medium"}\n```'))


if __name__ == "__main__":
    unittest.main()
