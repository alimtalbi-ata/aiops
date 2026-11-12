import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch
p=Path(__file__).resolve().parents[2]/"scripts/ops/live_usecase_qualification.py"
s=importlib.util.spec_from_file_location("live",p)
m=importlib.util.module_from_spec(s)
s.loader.exec_module(m)
def linkage():
    return {"run_id":m.RUN_ID,"database":{"run":{"status":"BLOCKED"}},"checks":{
        "core_run":"PASS","core_api":"PASS","evidence_api":"PASS",
        "critic_policy_outbox":"PASS","temporal_worker_execution":"UNVERIFIED",
        "hitl_action_binding":"UNVERIFIED","glpi_core_link":"MISSING","itsm_readback":"UNVERIFIED"}}
def portal():
    return {"status":"PASS","state":"running","health":"NOT_CONFIGURED"}
def platform():
    return {"verdict":"PASS","runtime":{"aiops2-rebuild-portal":{"state":"running"},
                                       "aiops2-rebuild-intelligence":{"state":"running"}}}
class LiveQualificationTests(unittest.TestCase):
    def test_real_existing_blockers_are_not_masked(self):
        result=m.summarize(linkage(),platform(),{},"2026-11-08T15:00Z",portal())
        self.assertEqual(result["verdict"],"HOLD")
        self.assertNotIn("temporal_worker_history",result["blocking"])
        self.assertEqual(next(x for x in result["checks"] if x["name"]=="temporal_worker_history")["status"],"NOT_APPLICABLE")
        self.assertIn("itsm_cross_reference",result["blocking"])
        self.assertEqual(next(x for x in result["checks"] if x["name"]=="critic_policy_outbox")["status"],"PASS")
    def test_missing_probe_fails_closed(self):
        result=m.summarize({}, {}, {}, "2026-11-08T15:00Z")
        self.assertEqual(result["verdict"],"HOLD")
        self.assertIn("platform_smoke",result["blocking"])
    def test_full_evidence_passes(self):
        l=linkage()
        l["checks"].update({"temporal_worker_execution":"PASS","hitl_action_binding":"PASS",
                            "glpi_core_link":"PASS","itsm_readback":"PASS"})
        self.assertEqual(m.summarize(l,platform(),{},"2026-11-08T15:00Z",portal())["verdict"],"PASS")
    def test_failed_platform_gate_fails(self):
        p=platform()
        p["verdict"]="HOLD"
        p["failures"]=["worker:HEALTH_NOT_200"]
        r=m.summarize(linkage(),p,{},"2026-11-08T15:00Z",portal())
        self.assertIn("platform_smoke",r["blocking"])
        self.assertIn("worker:HEALTH_NOT_200",str(r))
    def test_nonblocked_run_requires_real_temporal_and_hitl_proof(self):
        l=linkage()
        l["database"]["run"]["status"]="RUNNING"
        result=m.summarize(l,platform(),{},"2026-11-08T15:00Z",portal())
        self.assertIn("temporal_worker_history",result["blocking"])
        self.assertIn("hitl_action_binding",result["blocking"])
    def test_denied_run_requires_policy_outbox(self):
        l=linkage()
        l["checks"]["critic_policy_outbox"]="UNVERIFIED"
        result=m.summarize(l,platform(),{},"2026-11-08T15:00Z",portal())
        self.assertIn("policy_denial_safety",result["blocking"])
    def test_portal_absent_is_not_falsely_passed(self):
        r=m.summarize(linkage(),platform(),{},"2026-11-08T15:00Z")
        self.assertIn("portal_runtime",r["blocking"])
    def test_portal_running_is_verified_independently(self):
        with patch.object(m.subprocess,"run") as run:
            run.return_value.returncode=0
            run.return_value.stdout='{"Status":"running"}'
            self.assertEqual(m.portal_probe()["status"],"PASS")
            self.assertEqual(run.call_args.args[0][:2],["docker","inspect"])
    def test_portal_inspect_error_fails_closed(self):
        with patch.object(m.subprocess,"run") as run:
            run.return_value.returncode=1
            self.assertEqual(m.portal_probe()["status"],"UNVERIFIED")
    def test_runner_does_not_mutate_runtime(self):
        src=p.read_text()
        for forbidden in ("docker restart","docker compose up","method='POST'","DELETE FROM","UPDATE aiops."):
            self.assertNotIn(forbidden,src)
if __name__=="__main__":
    unittest.main()
