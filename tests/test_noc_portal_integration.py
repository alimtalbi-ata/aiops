import unittest
from datetime import datetime, timezone
from demo.noc_portal_integration import (validate_noc_runtime_snapshot, public_noc_snapshot,
                                         public_component_registry, create_noc_router, render_noc_dashboard)
from unittest.mock import patch
import sys
import types
from demo.star_n8n_identity_gate import STAGES

def handoff():
    identity = {"run_id":"RUN-001","incident_id":"INC-001",
                "correlation_id":"CORR-001"}
    return {stage:dict(identity) for stage in STAGES}

def data():
    return {"schema":"aiops-noc-runtime-readmodel-v1",
            "provenance":"RUNTIME_READMODEL","runtime_authenticated":True,
            "live_remediation_authorized":False,"run_id":"RUN-001","incident_id":"INC-001",
            "observed_at":"2026-10-20T12:00:00Z",
            "steps":[{"name":"detect","state":"WARN"}]}
class PortalNocContractTests(unittest.TestCase):
    def test_verified_read_model_accepted(self):self.assertEqual(validate_noc_runtime_snapshot(data(),now_utc="2026-10-20T12:01:00Z")["run_id"],"RUN-001")
    def test_synthetic_not_promoted(self):
        d=data();d["provenance"]="SYNTHETIC"
        with self.assertRaises(ValueError):validate_noc_runtime_snapshot(d)
    def test_no_source_fails_closed(self):
        with self.assertRaises(ValueError):validate_noc_runtime_snapshot({})
    def test_action_claim_rejected(self):
        d=data();d["live_remediation_authorized"]=True
        with self.assertRaises(ValueError):validate_noc_runtime_snapshot(d)
    def test_unknown_step_rejected(self):
        d=data();d["steps"][0]["state"]="REMEDIATED"
        with self.assertRaisesRegex(ValueError,"invalid timeline step"):
            validate_noc_runtime_snapshot(d,now_utc="2026-10-20T12:01:00Z")

    def test_unhashable_timeline_states_fail_closed(self):
        for invalid in ([], {}, {"state":"WARN"}):
            d=data();d["steps"][0]["state"]=invalid
            with self.subTest(invalid=invalid),self.assertRaisesRegex(
                    ValueError,"invalid timeline step"):
                validate_noc_runtime_snapshot(d,now_utc="2026-10-20T12:01:00Z")
    def test_stale_live_snapshot_fails_closed(self):
        with self.assertRaisesRegex(ValueError,"stale or future"):
            validate_noc_runtime_snapshot(data(),now_utc="2026-10-20T12:06:00Z")
    def test_future_snapshot_fails_closed(self):
        with self.assertRaisesRegex(ValueError,"stale or future"):
            validate_noc_runtime_snapshot(data(),now_utc="2026-10-20T11:59:59Z")
    def test_exact_freshness_boundary(self):
        self.assertEqual(validate_noc_runtime_snapshot(
            data(),now_utc="2026-10-20T12:05:00Z")["incident_id"],"INC-001")
    def test_invalid_freshness_policy_rejected(self):
        for invalid in (0,True,3601,"300"):
            with self.subTest(invalid=invalid),self.assertRaisesRegex(ValueError,"freshness policy"):
                validate_noc_runtime_snapshot(data(),max_age_seconds=invalid)
    def test_invalid_injected_clock_rejected(self):
        for invalid in ("2026-10-20T12:01:00+02:00","not-a-clock",123):
            with self.subTest(invalid=invalid),self.assertRaisesRegex(ValueError,"NOC clock"):
                validate_noc_runtime_snapshot(data(),now_utc=invalid)
    def test_public_projection_redacts_private_provider_fields(self):
        d=data()
        d["api_token"]="SYNTHETIC-DO-NOT-PUBLISH"
        d["upstream_headers"]={"Authorization":"SYNTHETIC"}
        d["steps"][0]["private_note"]="SYNTHETIC-PRIVATE"
        view=public_noc_snapshot(d,now_utc="2026-10-20T12:01:00Z")
        self.assertEqual(view["run_id"],"RUN-001")
        self.assertEqual(view["steps"],[{"name":"detect","state":"WARN"}])
        self.assertEqual(set(view),{"schema","provenance","runtime_authenticated",
                                    "live_remediation_authorized","run_id","incident_id",
                                    "observed_at","steps","ticket_id","evidence_sha256",
                                    "evidence_status","evidence_runtime_attested",
                                    "correlation_id","handoff_status","handoff_identity_sha256",
                                    "handoff_runtime_authenticated"})
        self.assertNotIn("api_token",view)
        self.assertNotIn("upstream_headers",view)
        self.assertNotIn("private_note",view["steps"][0])
        self.assertEqual(d["steps"][0]["private_note"],"SYNTHETIC-PRIVATE")

    def test_optional_ticket_and_evidence_correlation_is_explicitly_unverified(self):
        d=data()
        d["ticket_id"]="GLPI-12345"
        d["evidence_sha256"]="a"*64
        d["evidence_runtime_attested"]=False
        view=public_noc_snapshot(d,now_utc="2026-10-20T12:01:00Z")
        self.assertEqual(view["ticket_id"],"GLPI-12345")
        self.assertEqual(view["evidence_sha256"],"a"*64)
        self.assertEqual(view["evidence_status"],"UNVERIFIED_DIGEST")
        self.assertIs(view["evidence_runtime_attested"],False)

    def test_missing_correlation_remains_explicitly_absent(self):
        view=public_noc_snapshot(data(),now_utc="2026-10-20T12:01:00Z")
        self.assertIsNone(view["ticket_id"])
        self.assertIsNone(view["evidence_sha256"])
        self.assertEqual(view["evidence_status"],"ABSENT")
        self.assertIs(view["evidence_runtime_attested"],False)

    def test_invalid_ticket_and_evidence_claims_fail_closed(self):
        for key,invalid in (
            ("ticket_id","secret with spaces"),
            ("ticket_id","x"*101),
            ("ticket_id",42),
            ("evidence_sha256","bad-digest"),
            ("evidence_sha256","A"*64),
            ("evidence_runtime_attested",True),
            ("evidence_runtime_attested","true"),
        ):
            with self.subTest(key=key,invalid=invalid):
                d=data()
                d[key]=invalid
                with self.assertRaises(ValueError):
                    public_noc_snapshot(d,now_utc="2026-10-20T12:01:00Z")

    def test_public_projection_does_not_alias_provider_timeline(self):
        d=data()
        view=public_noc_snapshot(d,now_utc="2026-10-20T12:01:00Z")
        view["steps"][0]["state"]="CRIT"
        self.assertEqual(d["steps"][0]["state"],"WARN")

    def test_public_projection_rejects_unverified_or_stale_source(self):
        d=data()
        d["runtime_authenticated"]=False
        with self.assertRaises(ValueError):
            public_noc_snapshot(d,now_utc="2026-10-20T12:01:00Z")
        d["runtime_authenticated"]=True
        with self.assertRaisesRegex(ValueError,"stale or future"):
            public_noc_snapshot(d,now_utc="2026-10-20T12:10:00Z")

    def test_handoff_absence_is_explicit_and_never_authenticated(self):
        view=public_noc_snapshot(data(),now_utc="2026-10-20T12:01:00Z")
        self.assertEqual(view["handoff_status"],"ABSENT")
        self.assertIsNone(view["correlation_id"])
        self.assertIsNone(view["handoff_identity_sha256"])
        self.assertIs(view["handoff_runtime_authenticated"],False)

    def test_handoff_consistency_reuses_canonical_gate_without_exposing_stages(self):
        d=data();d["correlation_id"]="CORR-001";d["handoff_02_03"]=handoff()
        view=public_noc_snapshot(d,now_utc="2026-10-20T12:01:00Z")
        self.assertEqual(view["handoff_status"],"CONSISTENT_UNAUTHENTICATED")
        self.assertEqual(view["correlation_id"],"CORR-001")
        self.assertEqual(len(view["handoff_identity_sha256"]),64)
        self.assertIs(view["handoff_runtime_authenticated"],False)
        self.assertNotIn("handoff_02_03",view)
        page=render_noc_dashboard(
            view,public_component_registry(now_utc="2026-10-25T12:01:00Z"))
        self.assertIn("CONSISTENT_UNAUTHENTICATED",page)
        self.assertIn("exécution non authentifiée",page)

    def test_handoff_02_03_refuses_missing_or_divergent_stages(self):
        for mutation in ("missing","divergent","shadow"):
            with self.subTest(mutation=mutation):
                d=data();d["correlation_id"]="CORR-001";d["handoff_02_03"]=handoff()
                if mutation=="missing":
                    del d["handoff_02_03"]["rag_02"]
                elif mutation=="divergent":
                    d["handoff_02_03"]["prepare_analyst_03"]["incident_id"]="INC-OTHER"
                else:
                    d["handoff_02_03"]["canonical_02"]["runId"]="RUN-FORGED"
                with self.assertRaisesRegex(ValueError,"invalid 02->03 handoff"):
                    public_noc_snapshot(d,now_utc="2026-10-20T12:01:00Z")

    def test_handoff_must_match_noc_identity_and_correlation(self):
        for field,value in (("run_id","RUN-OTHER"),("incident_id","INC-OTHER"),
                            ("correlation_id","CORR-OTHER"),("correlation_id",None)):
            with self.subTest(field=field,value=value):
                d=data();d["correlation_id"]="CORR-001";d["handoff_02_03"]=handoff()
                d[field]=value
                with self.assertRaises(ValueError):
                    public_noc_snapshot(d,now_utc="2026-10-20T12:01:00Z")

    def test_forged_handoff_runtime_attestation_is_denied(self):
        d=data();d["handoff_runtime_authenticated"]=True
        with self.assertRaisesRegex(ValueError,"unsupported handoff"):
            public_noc_snapshot(d,now_utc="2026-10-20T12:01:00Z")
        view=public_noc_snapshot(data(),now_utc="2026-10-20T12:01:00Z")
        view["handoff_runtime_authenticated"]=True
        with self.assertRaisesRegex(ValueError,"unverified NOC dashboard"):
            render_noc_dashboard(
                view,public_component_registry(now_utc="2026-10-25T12:01:00Z"))


class PortalComponentBindingTests(unittest.TestCase):
    def test_dashboard_displays_20_components_without_unverified_links(self):
        view=public_noc_snapshot(data(),now_utc="2026-10-20T12:01:00Z")
        registry=public_component_registry(now_utc="2026-10-25T12:01:00Z")
        page=render_noc_dashboard(view,registry)
        self.assertEqual(page.count('class="component-row"'),20)
        self.assertIn("Thruk operations",page)
        self.assertIn("/observability/grafana",page)
        self.assertIn("NON ATTESTÉE",page)
        self.assertNotIn("<a href=",page)

    def test_dashboard_escapes_untrusted_incident_timeline(self):
        d=data()
        d["steps"][0]["name"]="<script>alert(1)</script>"
        view=public_noc_snapshot(d,now_utc="2026-10-20T12:01:00Z")
        page=render_noc_dashboard(
            view,public_component_registry(now_utc="2026-10-25T12:01:00Z"))
        self.assertIn("&lt;script&gt;",page)
        self.assertNotIn("<script>",page)

    def test_dashboard_rejects_forged_route_attestation(self):
        view=public_noc_snapshot(data(),now_utc="2026-10-20T12:01:00Z")
        for field,value in (("available_in_portal",True),("path","/evil")):
            registry=public_component_registry(now_utc="2026-10-25T12:01:00Z")
            registry["items"][0][field]=value
            with self.subTest(field=field),self.assertRaisesRegex(
                    ValueError,"contradictory or unattested"):
                render_noc_dashboard(view,registry)

    def test_dashboard_rejects_unhashable_component_state(self):
        view=public_noc_snapshot(data(),now_utc="2026-10-20T12:01:00Z")
        for invalid in ([], {}):
            registry=public_component_registry(now_utc="2026-10-25T12:01:00Z")
            registry["items"][0]["state"]=invalid
            with self.subTest(invalid=invalid),self.assertRaisesRegex(
                    ValueError,"contradictory or unattested component route"):
                render_noc_dashboard(view,registry)

    def test_no_host_provider_keeps_all_routes_unverified(self):
        registry=public_component_registry(now_utc="2026-10-25T12:01:00Z")
        self.assertEqual(len(registry["items"]),20)
        self.assertTrue(all(item["state"]=="UNKNOWN" and
                            item["available_in_portal"] is False and
                            item["requires_route_integration"] is True
                            for item in registry["items"]))

    def test_fresh_host_observation_updates_state_not_route_attestation(self):
        observations={"thruk":{"state":"WARN","observed_at":"2026-10-25T12:00:00Z",
                               "authenticated":True}}
        registry=public_component_registry(lambda:observations,
                                           now_utc="2026-10-25T12:01:00Z")
        thruk=next(item for item in registry["items"] if item["id"]=="thruk")
        self.assertEqual(thruk["state"],"WARN")
        self.assertFalse(thruk["available_in_portal"])
        self.assertTrue(thruk["requires_route_integration"])
        stale=public_component_registry(lambda:observations,
                                        now_utc="2026-10-25T12:06:00Z")
        self.assertEqual(next(item for item in stale["items"]
                              if item["id"]=="thruk")["state"],"UNKNOWN")

    def test_bad_provider_fails_closed(self):
        for provider in (42, lambda:None, lambda:{"unknown":{}},
                         lambda:{"thruk":{"state":"OK","authenticated":True}},
                         lambda:(_ for _ in ()).throw(RuntimeError("PRIVATE-SECRET"))):
            with self.subTest(provider=repr(provider)), self.assertRaises(Exception):
                public_component_registry(provider,now_utc="2026-10-25T12:01:00Z")

    def test_http_component_route_uses_provider_and_redacts_failures(self):
        class FakeRouter:
            def __init__(self):self.routes={}
            def get(self,path,response_class=None):
                def register(handler):
                    self.routes[path]=handler
                    return handler
                return register
        class FakeHTTPException(Exception):
            def __init__(self,status_code,detail):
                self.status_code=status_code
                self.detail=detail
        fake_fastapi=types.ModuleType("fastapi")
        fake_fastapi.APIRouter=FakeRouter
        fake_fastapi.HTTPException=FakeHTTPException
        fake_responses=types.ModuleType("fastapi.responses")
        fake_responses.HTMLResponse=object
        now=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        observations={"thruk":{"state":"OK","observed_at":now,"authenticated":True}}
        with patch.dict(sys.modules,{"fastapi":fake_fastapi,
                                     "fastapi.responses":fake_responses}):
            router=create_noc_router(lambda:data(),lambda:observations)
            view=router.routes["/api/platform/components"]()
            self.assertEqual(next(x for x in view["items"] if x["id"]=="thruk")["state"],"OK")
            self.assertFalse(next(x for x in view["items"] if x["id"]=="thruk")["available_in_portal"])
            failed=create_noc_router(lambda:data(),
                                     lambda:(_ for _ in ()).throw(RuntimeError("PRIVATE-SECRET")))
            with self.assertRaises(FakeHTTPException) as caught:
                failed.routes["/api/platform/components"]()
            self.assertEqual(caught.exception.status_code,503)
            self.assertNotIn("PRIVATE-SECRET",caught.exception.detail)


class HttpNocReadModelRouteTests(unittest.TestCase):
    def _mount(self, read_model):
        class FakeRouter:
            def __init__(self): self.routes={}
            def get(self,path,response_class=None):
                def register(handler):
                    self.routes[path]=handler
                    return handler
                return register
        class FakeHTTPException(Exception):
            def __init__(self,status_code,detail):
                self.status_code=status_code
                self.detail=detail
        fake_fastapi=types.ModuleType("fastapi")
        fake_fastapi.APIRouter=FakeRouter
        fake_fastapi.HTTPException=FakeHTTPException
        fake_responses=types.ModuleType("fastapi.responses")
        fake_responses.HTMLResponse=object
        patcher=patch.dict(sys.modules,{"fastapi":fake_fastapi,
                                       "fastapi.responses":fake_responses})
        patcher.start()
        self.addCleanup(patcher.stop)
        return create_noc_router(read_model),FakeHTTPException

    def test_http_noc_route_projects_only_allowlisted_fields(self):
        payload=data()
        payload["observed_at"]=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        payload["api_token"]="DO-NOT-LEAK"
        router,_=self._mount(lambda:payload)
        view=router.routes["/api/noc/state"]()
        self.assertEqual(view["run_id"],"RUN-001")
        self.assertNotIn("api_token",view)
        self.assertIs(view["live_remediation_authorized"],False)

    def test_http_noc_route_fails_closed_for_synthetic_and_provider_errors(self):
        synthetic=data()
        synthetic["observed_at"]=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        synthetic["provenance"]="SYNTHETIC"
        for provider in (lambda:synthetic,
                         lambda:(_ for _ in ()).throw(RuntimeError("PRIVATE-SECRET")),
                         lambda:None):
            with self.subTest(provider=repr(provider)):
                router,exc=self._mount(provider)
                with self.assertRaises(exc) as caught:
                    router.routes["/api/noc/state"]()
                self.assertEqual(caught.exception.status_code,503)
                self.assertNotIn("PRIVATE-SECRET",caught.exception.detail)

if __name__=="__main__":unittest.main()
