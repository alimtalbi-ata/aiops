import unittest
from portal.acme_workbench_presentation import render_story_context

class WorkbenchPresentation(unittest.TestCase):
    def test_missing(self):
        self.assertIn("MISSING", render_story_context({}))

    def test_foreign_or_unqualified(self):
        for value in ({"story_identity": {}, "binding": {}}, {"runtime_attested": True}):
            result = render_story_context({"twin_consumer": value, "signal_context": {}})
            self.assertIn("UNKNOWN", result)
            self.assertNotIn("STORY_OFFLINE — UNBOUND", result)


    def test_runtime_refusals(self):
        from portal.acme_workbench_presentation import render_runtime_refusals
        base = dict(schema="aiops.acme.runtime-context.v1", scope="RUNTIME_SANDBOX",
                    binding_status="UNBOUND", runtime_attested=False,
                    live_remediation_authorized=False, runtime_freshness="UNKNOWN")
        for value, expected in [(None, "MISSING"), ({}, "UNKNOWN"),
            (dict(base, qualification="BLOCK"), "UNKNOWN — BLOCK"),
            (dict(base, qualification="REJECT"), "FAIL — REJECT"),
            (dict(base, qualification="PASS"), "UNKNOWN — UNKNOWN"),
            (dict(base, qualification="REJECT", runtime_attested=True), "UNKNOWN — UNKNOWN")]:
            with self.subTest(value=value):
                html = render_runtime_refusals(value)
                self.assertIn(expected, html)
                self.assertIn("Terminal C : MISSING", html)
                self.assertIn("Qualification runtime : UNKNOWN", html)
                self.assertNotIn("RESOLVED", html)
                self.assertIn("NO-GO", html)
