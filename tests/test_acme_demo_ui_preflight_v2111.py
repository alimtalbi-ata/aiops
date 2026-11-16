import io,unittest
from pathlib import Path
import importlib.util
p=Path(__file__).resolve().parents[1]/"tools/acme_demo_ui_preflight_v2111.py"
spec=importlib.util.spec_from_file_location("demo_ui",p)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class Response:
    status=200
    def __init__(self,html):self.html=html
    def __enter__(self):return self
    def __exit__(self,*args):return False
    def read(self,n):return self.html.encode()
class ReadinessTests(unittest.TestCase):
    def test_story_missing_controls_is_rejected(self):
        checks=m.probe("http://example",lambda url,timeout:Response("empty"))
        story=next(x for x in checks if x["path"]=="/policy-story")
        self.assertEqual(story["status"],"FAIL")
    def test_story_with_controls_passes(self):
        text="story-next story-reset STOP_AUTO FICTIF / SANS EFFET"
        checks=m.probe("http://example",lambda url,timeout:Response(text))
        self.assertTrue(all(x["status"]=="PASS" for x in checks))
if __name__=="__main__":unittest.main()
