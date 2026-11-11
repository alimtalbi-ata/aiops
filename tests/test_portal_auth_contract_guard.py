"""Static guard: portal must not claim tenant-qualified evidence without trusted identity.

This is a regression tripwire, NOT an end-to-end authorization acceptance test.
It deliberately asserts the current unqualified state until an authenticated,
server-scoped projection and its negative tests are implemented.
"""
import ast
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
PORTAL = ROOT / "app" / "portal" / "main.py"
CORE = ROOT / "app" / "core" / "main.py"
MODULE = ROOT / "app" / "portal" / "components" / "operational_state.mjs"


class PortalAuthContractGuard(unittest.TestCase):
    def test_bootstrap_does_not_forge_authorization_attestation(self):
        source = PORTAL.read_text(encoding="utf-8")
        tree = ast.parse(source)
        bootstrap = next(n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == "bootstrap")
        body = ast.get_source_segment(source, bootstrap)
        self.assertNotIn("scope_verified", body)
        self.assertNotIn("authorization_source", body)
        self.assertNotIn("observed_at", body)

    def test_client_requires_explicit_server_attestation(self):
        source = MODULE.read_text(encoding="utf-8")
        self.assertIn("result.scope_verified===true", source)
        self.assertIn("result.authorization_source==='server'", source)
        self.assertIn("result.observed_at", source)

    def test_global_core_reads_not_mistaken_for_tenant_scoped_projections(self):
        source = CORE.read_text(encoding="utf-8")
        tree = ast.parse(source)
        for name in ("dashboard", "list_runs"):
            function = next(n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name)
            segment = ast.get_source_segment(source, function)
            self.assertNotIn("scope_verified", segment)
            self.assertNotIn("authorization_source", segment)


if __name__ == "__main__":
    unittest.main()
