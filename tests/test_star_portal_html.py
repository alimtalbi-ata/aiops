import unittest
from html.parser import HTMLParser
from demo.star_snapshot_choreography import CUES
from demo.star_portal_html import render_storyboard

class Structure(HTMLParser):
    def __init__(self):
        super().__init__()
        self.scripts = 0
        self.frames = 0
    def handle_starttag(self, tag, attrs):
        self.scripts += tag in ("script","iframe","form","img")
        self.frames += tag == "li"

class StarPortalHTMLTests(unittest.TestCase):
    def report(self):
        return {"schema":"star-capture-evidence-v1",
                "entries":[{"cue":c.cue,"status":"missing"} for c in CUES]}

    def test_nine_static_cues(self):
        page=render_storyboard(self.report(),"SAN_FABRIC_P1")
        parser=Structure()
        parser.feed(page)
        self.assertEqual(parser.frames, 9)
        self.assertEqual(parser.scripts, 0)
        self.assertIn("aucune capture ne prouve seule",page)

    def test_fake_image_is_labeled_and_no_raw_source(self):
        r=self.report()
        r["entries"][0]["status"]="simulated"
        r["entries"][0]["source_url"]="http://user:secret@example.com/path"
        page=render_storyboard(r,"PAYMENTS_P2")
        self.assertIn("Illustration fictive",page)
        self.assertNotIn("secret",page)
        self.assertNotIn("example.com",page)

    def test_rejects_malicious_extra_cue(self):
        r=self.report()
        r["entries"].append({"cue":"inject","status":"missing"})
        with self.assertRaises(ValueError):
            render_storyboard(r,"SAN_FABRIC_P1")

if __name__=="__main__":
    unittest.main()
