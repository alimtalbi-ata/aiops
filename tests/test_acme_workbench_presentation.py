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
