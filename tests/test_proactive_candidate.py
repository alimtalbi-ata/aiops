import importlib.util
from pathlib import Path

spec=importlib.util.spec_from_file_location("candidate",Path(__file__).resolve().parents[1]/"deploy/proactive_candidate.py")
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

def test_candidate_gates():
    sha="a"*40
    pr={"state":"open","head":{"sha":sha,"repo":{"full_name":m.REPO}}}
    checks=[{"id":i,"name":n,"head_sha":sha,"app":{"slug":"github-actions"},"status":"completed","conclusion":"success"} for i,n in enumerate(sorted(m.REQUIRED))]
    assert m.classify(pr,checks)=="BUILD_ELIGIBLE"
    assert m.classify(pr,checks[:-1])=="CI_PENDING"
    assert m.classify(pr,checks+[dict(checks[0],id=99,conclusion="failure")])=="CI_BLOCKED"
    assert m.classify(pr,[dict(c,head_sha="b"*40) for c in checks])=="CI_PENDING"
    assert m.classify(dict(pr,state="closed"),checks)=="INELIGIBLE"
    foreign=[dict(c,id=999,app={"slug":"untrusted-app"},conclusion="failure") for c in checks]
    assert m.classify(pr,checks+foreign)=="BUILD_ELIGIBLE"
    no_app=[dict(c,app={}) for c in checks]
    assert m.classify(pr,no_app)=="CI_PENDING"

def test_success_conclusion_is_not_eligible_until_check_completed():
    sha="c"*40
    pr={"state":"open","head":{"sha":sha,"repo":{"full_name":m.REPO}}}
    checks=[{"id":i,"name":n,"head_sha":sha,"app":{"slug":"github-actions"},"status":"in_progress","conclusion":"success"} for i,n in enumerate(sorted(m.REQUIRED))]
    assert m.classify(pr,checks)=="CI_PENDING"
    completed=[dict(c,status="completed") for c in checks]
    assert m.classify(pr,completed)=="BUILD_ELIGIBLE"


def test_fetch_check_runs_reads_all_pages(monkeypatch):
    import json
    sha="d"*40
    first=[{"id":i,"name":f"check-{i}"} for i in range(100)]
    second=[{"id":100,"name":"check-100"}]
    pages=[{"total_count":101,"check_runs":first},{"total_count":101,"check_runs":second}]
    calls=[]
    def fake_check_output(args,timeout):
        calls.append(args)
        return json.dumps(pages).encode()
    monkeypatch.setattr(m.subprocess,"check_output",fake_check_output)
    checks=m.fetch_check_runs(sha)
    assert len(checks)==101
    assert checks[-1]["id"]==100
    assert "--paginate" in calls[0] and "--slurp" in calls[0]


def test_fetch_check_runs_rejects_incomplete_or_duplicate_pages(monkeypatch):
    import json
    import pytest
    sha="e"*40
    cases=[
        [{"total_count":2,"check_runs":[{"id":1}]}],
        [{"total_count":2,"check_runs":[{"id":1}]},{"total_count":2,"check_runs":[{"id":1}]}],
        [{"total_count":2,"check_runs":[{"id":1}]},{"total_count":3,"check_runs":[{"id":2}]}],
    ]
    for pages in cases:
        monkeypatch.setattr(m.subprocess,"check_output",lambda args,timeout,p=pages:json.dumps(p).encode())
        with pytest.raises(ValueError):
            m.fetch_check_runs(sha)
