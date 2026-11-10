"""Regression: FS147 read-only probe must remain importable Python source.

This test catches accidental literal backslash-n tokens in the multi-line
URL guard, which otherwise make the live qualification probe unusable.
"""
import ast
import pathlib
import unittest


class TwinProbeSyntaxContract(unittest.TestCase):
    def test_probe_parses_and_compiles(self):
        path = pathlib.Path(__file__).resolve().parents[1] / "scripts/fs/fs147_twin_live_readonly_probe.py"
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        compile(tree, str(path), "exec")
        self.assertTrue(any(isinstance(node, ast.FunctionDef) and node.name == "fetch_json"
                            for node in ast.walk(tree)))

    def test_url_guard_has_real_line_breaks(self):
        path = pathlib.Path(__file__).resolve().parents[1] / "scripts/fs/fs147_twin_live_readonly_probe.py"
        source = path.read_text(encoding="utf-8")
        self.assertIn('or not parsed.hostname\n            or parsed.username', source)
        self.assertNotIn('or not parsed.hostname\\n            or parsed.username', source)


if __name__ == "__main__":
    unittest.main()
