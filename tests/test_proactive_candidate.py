import importlib.util
from pathlib import Path

spec=importlib.util.spec_from_file_location("candidate",Path(__file__).resolve().parents[1]/"deploy/proactive_candidate.py")
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

def test_candidate_gates():
    sha="a"*40
    pr={"state":"open","head":{"sha":sha,"repo":{"full_name":m.REPO}}}
    checks=[{"id":i,"name":n,"head_sha":sha,"status":"completed","conclusion":"success"} for i,n in enumerate(sorted(m.REQUIRED))]
    assert m.classify(pr,checks)=="BUILD_ELIGIBLE"
    assert m.classify(pr,checks[:-1])=="CI_PENDING"
    assert m.classify(pr,checks+[dict(checks[0],id=99,conclusion="failure")])=="CI_BLOCKED"
    assert m.classify(pr,[dict(c,head_sha="b"*40) for c in checks])=="CI_PENDING"
    assert m.classify(dict(pr,state="closed"),checks)=="INELIGIBLE"
