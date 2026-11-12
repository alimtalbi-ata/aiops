import datetime as dt
import importlib.util
from pathlib import Path
import unittest

p=Path(__file__).resolve().parents[2]/"scripts/ops/platform_gap_analyzer.py"
spec=importlib.util.spec_from_file_location("gap",p)
gap=importlib.util.module_from_spec(spec)
spec.loader.exec_module(gap)
NOW=dt.datetime(2026,11,8,15,0,tzinfo=dt.timezone.utc)

def report():
    return {"collected_at":NOW.isoformat(),"docker":{"available":True,"containers":[
      {"name":name,"state":"running","health":"healthy"} for name in gap.REQUIRED.values()]}}

class TestGaps(unittest.TestCase):
    def test_complete_runtime_is_not_e2e(self):
        r=gap.analyze(report(),now=NOW)
        codes={x["code"] for x in r["gaps"]}
        self.assertIn("E2E_NOT_ATTESTED",codes)
        self.assertIn("DEPLOY_NOT_ATTESTED",codes)
        self.assertIn("PLATFORM_GATE_MISSING",codes)
        self.assertFalse(any(x.startswith("MISSING_") for x in codes))
    def test_missing_core_is_p0(self):
        r=report()
        r["docker"]["containers"]=[x for x in r["docker"]["containers"] if x["name"]!="aiops2-rebuild-core"]
        result=gap.analyze(r,now=NOW)
        self.assertEqual(result["gaps"][0]["code"],"MISSING_CORE")
        self.assertEqual(result["gaps"][0]["severity"],"P0")
    def test_stale_minute_report(self):
        r=report()
        r["collected_at"]="2026-11-08T14:50:00+00:00"
        self.assertIn("REPORT_STALE",{x["code"] for x in gap.analyze(r,now=NOW)["gaps"]})
    def test_platform_gate_pass(self):
        platform={"utc":NOW.isoformat(),"verdict":"PASS","probes":{p:{"http":200} for p in gap.PROBES}}
        codes={x["code"] for x in gap.analyze(report(),platform,now=NOW)["gaps"]}
        self.assertNotIn("PLATFORM_GATE_MISSING",codes)
        self.assertFalse(any(x.startswith("PROBE_") for x in codes))
    def test_platform_gate_failure(self):
        platform={"utc":NOW.isoformat(),"verdict":"HOLD","probes":{}}
        codes={x["code"] for x in gap.analyze(report(),platform,now=NOW)["gaps"]}
        self.assertIn("PLATFORM_GATE_HOLD",codes)
        self.assertIn("PROBE_CORE",codes)

if __name__=="__main__":
    unittest.main()
