import unittest
from html.parser import HTMLParser
from demo.star_snapshot_choreography import CUES
from demo.star_navigable_preview import render_navigator

class Parser(HTMLParser):
    def __init__(self):
        super().__init__(); self.links=[]; self.ids=[]; self.unsafe=[]
    def handle_starttag(self, tag, attrs):
        d=dict(attrs)
        if tag=="a": self.links.append(d.get("href"))
        if tag=="section": self.ids.append(d.get("id"))
        if tag in ("script","iframe","form","img"): self.unsafe.append(tag)

class NavigationTests(unittest.TestCase):
    def report(self, scenario):
        return {"schema":"star-portal-transport-v1","scenario":scenario,
                "safety":{"read_only":True,"runtime_authenticated":False,
                          "remediation_authorized":False},
                "frames":[{"step":c.cue,"application":c.service,"expected_view":c.view,
                           "capture_status":"missing","runtime_verified":False,
                           "action_allowed":False} for c in CUES]}
    def test_navigation_references_nine_local_sections(self):
        for name in ("SAN_FABRIC_P1","PAYMENTS_P2"):
            page=render_navigator(self.report(name),name)
            p=Parser();p.feed(page)
            self.assertEqual(len(p.ids),9)
            self.assertEqual(p.links,["#"+x for x in p.ids])
            self.assertEqual(p.unsafe,[])
            self.assertIn("Capture absente",page)
    def test_capture_status_fails_closed(self):
        r=self.report("SAN_FABRIC_P1")
        r["frames"][0]["capture_status"]="verified"
        with self.assertRaises(ValueError):
            render_navigator(r,"SAN_FABRIC_P1")
    def test_malicious_metadata_not_reflected(self):
        r=self.report("PAYMENTS_P2")
        r["token"]="<script>alert(1)</script>"
        page=render_navigator(r,"PAYMENTS_P2")
        self.assertNotIn("alert(1)",page)
        self.assertNotIn("<script",page)
if __name__=="__main__":unittest.main()
