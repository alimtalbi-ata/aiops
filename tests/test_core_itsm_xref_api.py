"""Adversarial HTTP tests; mocked DB, no GLPI/production requests."""
import os, json, hmac, hashlib, unittest, tempfile
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from core import itsm_xref as x

SOURCE_READBACK = x._glpi_readback  # real adapter; unit HTTP positives are synthetic mocks

NOW=datetime.now(timezone.utc)
TOKEN="ci-service-a"
KEY="ci-only-test-attestation-key-32bytes-long"
OWNER_KEY="independent-ci-owner-attestor-key-32-bytes"
PATH="/api/tenants/TEN-A/itsm/glpi/GLPI-A/tickets/123/xref"

def authz():
    def entry(token,tenant,permissions):
        return {"token_sha256":hashlib.sha256(token.encode()).hexdigest(),
                "actor_id":"svc-"+tenant,"tenant_ids":[tenant],"permissions":permissions}
    return json.dumps([entry(TOKEN,"TEN-A",["itsm:xref:read"]),
                       entry("ci-service-b","TEN-B",["itsm:xref:read"]),
                       entry("ci-no-permission","TEN-A",[])])

def event(**changes):
    e=dict(association_id="XREF-A",tenant_id="TEN-A",glpi_instance_id="GLPI-A",
           ticket_id="123",glpi_entity_id="0",incident_id="INC-A",run_id="RUN-A",
           source_event_id="EVT-A",mapping_version=1,event_type="VERIFIED",
           actor_id="svc-glpi",observed_at=NOW-timedelta(seconds=20),
           known_at=NOW-timedelta(seconds=10),supersedes_association_id=None,
           verification_method="AUTHENTICATED_ID_READBACK",provenance="AUTHENTICATED_SOURCE_API",
           glpi_ticket_readback_verified=True,core_run_readback_verified=True,
           source_payload_hash="a"*64)
    e.update(changes)
    e["attestation_mac"]=hmac.new(KEY.encode(),x._payload(e),hashlib.sha256).hexdigest()
    return tuple(e[k] for k in x._COLUMNS)

OWNERS=[("incident","INC-A","TEN-A",True),("run","RUN-A","TEN-A",True),
        ("glpi_instance","GLPI-A","TEN-A",True),
        ("glpi_ticket","GLPI-A:123","TEN-A",True),
        ("glpi_entity","GLPI-A:0","TEN-A",True)]

class FakeDB:
    def __init__(self):
        self.events=[event()]
        self.owners=list(OWNERS)
        self.core=("INC-A","INC-A")
        self.calls=[]
        self.fail=False
    @contextmanager
    def connect(self): yield self
    def execute(self,sql,args):
        self.calls.append((sql,args))
        if self.fail: raise RuntimeError("ephemeral simulated DB failure")
        self.kind=("events" if "itsm_xref_events" in sql else
                   "core" if "from aiops.runs" in sql else "owners")
        return self
    def owner_rows(self):
        return [tuple(row)+("EVT-OWNER",NOW-timedelta(seconds=30),
                            NOW-timedelta(seconds=10)) if len(row)==4 else row
                for row in self.owners]
    def fetchall(self):
        return self.events if self.kind=="events" else self.owner_rows()
    def fetchone(self): return self.core

class XrefHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app=FastAPI()
        app.include_router(x.router)
        cls.client=TestClient(app)
    def setUp(self):
        self.fake=FakeDB()
        with tempfile.NamedTemporaryFile(mode="w",delete=False) as fp:
            self.proof_path=fp.name
        self.write_proofs()
        self.env=patch.dict(os.environ,{"AIOPS_XREF_READ_AUTHZ_JSON":authz(),
                                       "AIOPS_XREF_ATTESTATION_KEY":KEY,
                                       "AIOPS_XREF_OWNER_ATTESTATION_KEY":OWNER_KEY,
                                       "AIOPS_XREF_OWNER_PROOFS_PATH":self.proof_path})
        self.env.start()
        self.mock=patch.object(x,"db",self.fake.connect)
        self.mock.start()
        self.source_mock=patch.object(x,"_glpi_readback",return_value=True)
        self.source_mock.start()
    def write_proofs(self):
        proofs={}
        for row in self.fake.owner_rows():
            kind,rid,*_=row
            proofs[kind+"|"+rid]=hmac.new(OWNER_KEY.encode(),
                    x._owner_proof_payload(*row),hashlib.sha256).hexdigest()
        with open(self.proof_path,"w",encoding="utf-8") as fp:
            json.dump({"schema":"aiops.core-ownership-proof.v1","proofs":proofs},fp)
    def tearDown(self):
        self.source_mock.stop()
        self.mock.stop()
        self.env.stop()
        os.unlink(self.proof_path)
    def read(self,token=TOKEN,path=PATH,**params):
        headers={} if token is None else {"Authorization":"Bearer "+token}
        return self.client.get(path,headers=headers,params=params,follow_redirects=False)
    def hidden(self,r):
        self.assertNotIn("run_id",r.json())
        self.assertNotIn("incident_id",r.json())
        self.assertNotIn("ticket_id",r.json())
        self.assertEqual(r.headers.get("cache-control"),"no-store")
    def test_signed_verified_core_and_tenant_readback(self):
        r=self.read(expected_run_id="RUN-A",expected_incident_id="INC-A")
        self.assertEqual(r.status_code,200,r.text)
        self.assertEqual(r.json()["status"],"VERIFIED")
        self.assertEqual(r.json()["run_id"],"RUN-A")
        self.assertEqual(r.json()["source_event_id"],"EVT-A")
        self.assertEqual(len(self.fake.calls),3)
    def test_unsigned_or_rekeyed_ownership_never_verifies(self):
        with patch.dict(os.environ,{"AIOPS_XREF_OWNER_ATTESTATION_KEY":""}):
            r=self.read()
            self.assertEqual(r.json()["status"],"UNKNOWN")
            self.hidden(r)
        self.fake.calls.clear()
        # A signed xref event and verified=true DB row are insufficient.
        self.fake.owners[4]=("glpi_entity","GLPI-A:0","TEN-A",True,
                              "EVT-OWNER-FORGED",NOW-timedelta(seconds=30),
                              NOW-timedelta(seconds=10))
        r=self.read()
        self.assertEqual(r.json()["status"],"UNKNOWN")
        self.hidden(r)
        self.assertEqual(len(self.fake.calls),3)

    def test_no_independent_glpi_source_readback_is_unknown(self):
        # Even a valid HMAC, verified=true and exact Core Run/Incident are not
        # independent GLPI ticket/entity/CI authority.
        with patch.object(x, "_glpi_readback", return_value=False) as gate:
            r=self.read(expected_run_id="RUN-A",expected_incident_id="INC-A")
        self.assertEqual(r.status_code,200,r.text)
        self.assertEqual(r.json()["status"],"UNKNOWN")
        self.hidden(r)
        gate.assert_called_once()

    def test_real_glpi_adapter_requires_exact_source_and_pinned_transport(self):
        import requests
        from unittest.mock import patch as mock_patch

        entry={"tenant_id":"TEN-A","instance_id":"GLPI-A",
               "origin":"https://glpi.internal.example",
               "app_token":"app-token-for-ci-only",
               "session_token":"session-token-for-ci-only"}
        source={"glpi_entity_id":"0"}

        class Response:
            def __init__(self, data, status=200):
                self.status_code=status
                self.headers={"Content-Type":"application/json"}
                self.data=json.dumps(data).encode()
            def __enter__(self): return self
            def __exit__(self,*args): return False
            def iter_content(self,chunk_size=4096): yield self.data

        class Session:
            def __init__(self, records):
                self.records=records
                self.trust_env=True
                self.calls=[]
            def __enter__(self): return self
            def __exit__(self,*args): return False
            def get(self,url,**kwargs):
                self.calls.append(url)
                assert self.trust_env is False
                assert kwargs["allow_redirects"] is False
                assert kwargs["verify"] is True
                assert kwargs["stream"] is True
                assert url.startswith("https://glpi.internal.example/apirest.php/")
                return self.records[url.split("/apirest.php",1)[1]]

        good={"/Ticket/123":Response({"id":123,"entities_id":0}),
              "/Entity/0":Response({"id":0}),
              "/Ticket/123/Item_Ticket":Response([{"itemtype":"Computer","items_id":77}]),
              "/Computer/77":Response({"id":77,"entities_id":0})}
        with mock_patch.dict(os.environ,{"AIOPS_XREF_GLPI_READBACK_JSON":json.dumps([entry])}):
            session=Session(good)
            with mock_patch.object(requests,"Session",return_value=session):
                self.assertTrue(SOURCE_READBACK(source,"TEN-A","GLPI-A","123"))
                self.assertEqual(len(session.calls),4)
            for altered in (
                {**good,"/Ticket/123":Response({"id":123,"entities_id":1})},
                {**good,"/Computer/77":Response({"id":77,"entities_id":1})},
                {**good,"/Ticket/123/Item_Ticket":Response([])},
                {**good,"/Ticket/123":Response({"id":123,"entities_id":0},302)},
            ):
                with mock_patch.object(requests,"Session",return_value=Session(altered)):
                    self.assertFalse(SOURCE_READBACK(source,"TEN-A","GLPI-A","123"))
            with mock_patch.object(requests,"Session") as no_network:
                self.assertFalse(SOURCE_READBACK(source,"TEN-B","GLPI-A","123"))
                self.assertFalse(SOURCE_READBACK(source,"TEN-A","GLPI-B","123"))
                no_network.assert_not_called()
        with mock_patch.dict(os.environ,{"AIOPS_XREF_GLPI_READBACK_JSON":json.dumps([
                {**entry,"origin":"http://glpi.internal.example"}])}):
            with mock_patch.object(requests,"Session") as no_network:
                self.assertFalse(SOURCE_READBACK(source,"TEN-A","GLPI-A","123"))
                no_network.assert_not_called()

    def test_run_token_in_ticket_text_never_links(self):
        self.fake.events=[]
        r=self.read()
        self.assertEqual(r.status_code,404)
        self.hidden(r)
    def test_401_403_and_no_database_request(self):
        for token,code in ((None,401),("wrong",401),("ci-service-b",403),
                           ("ci-no-permission",403),(TOKEN+" extra",401)):
            with self.subTest(token=token):
                r=self.read(token=token)
                self.assertEqual(r.status_code,code,r.text)
                self.hidden(r)
        self.assertEqual(self.fake.calls,[])
    def test_missing_auth_config_or_key_and_db_unavailable_503(self):
        for name in ("AIOPS_XREF_READ_AUTHZ_JSON","AIOPS_XREF_ATTESTATION_KEY"):
            with patch.dict(os.environ,{name:""}):
                r=self.read()
                self.assertEqual(r.status_code,503)
                self.hidden(r)
        self.assertEqual(self.fake.calls,[])
        self.fake.fail=True
        r=self.read()
        self.assertEqual(r.status_code,503)
        self.hidden(r)
    def test_invalid_preflight_no_database_request(self):
        for params in ({"expected_run_id":"RUN-%2F"},
                       {"expected_incident_id":"INC/foreign"},
                       {"evidence_known_at":"2026-10-31T12:00:00"},
                       {"evidence_known_at":"0001-01-01T00:00:00Z"},
                       {"evidence_known_at":"9999-12-31T23:59:59Z"}):
            with self.subTest(params=params):
                r=self.read(**params)
                self.assertEqual(r.status_code,404)
                self.hidden(r)
        for path in (PATH.replace("/123/","/0/"),PATH.replace("TEN-A","TEN!A")):
            r=self.read(path=path)
            self.assertEqual(r.status_code,404)
            self.hidden(r)
        self.assertEqual(self.fake.calls,[])
    def test_stale_evidence_preflight_does_not_query_core(self):
        stale=(NOW-timedelta(minutes=10)).isoformat()
        r=self.read(evidence_known_at=stale)
        self.assertEqual(r.status_code,200,r.text)
        self.assertEqual(r.json()["status"],"STALE")
        self.hidden(r)
        future=(NOW+timedelta(minutes=1)).isoformat()
        r=self.read(evidence_known_at=future)
        self.assertEqual(r.status_code,404,r.text)
        self.hidden(r)
        self.assertEqual(self.fake.calls,[])
        fresh=(NOW-timedelta(seconds=20)).isoformat()
        r=self.read(evidence_known_at=fresh)
        self.assertEqual(r.json()["status"],"VERIFIED")
        self.assertEqual(len(self.fake.calls),3)

    def test_stale_evidence_requires_auth_and_tenant_acl_without_db(self):
        stale=(NOW-timedelta(minutes=10)).isoformat()
        for token,code in ((None,401),("wrong",401),
                           ("ci-service-b",403),("ci-no-permission",403)):
            with self.subTest(token=token):
                r=self.read(token=token,evidence_known_at=stale)
                self.assertEqual(r.status_code,code,r.text)
                self.hidden(r)
        self.assertEqual(self.fake.calls,[])
        # Valid scoped service may receive STALE without touching Core DB.
        r=self.read(evidence_known_at=stale)
        self.assertEqual(r.status_code,200,r.text)
        self.assertEqual(r.json()["status"],"STALE")
        self.hidden(r)
        self.assertEqual(self.fake.calls,[])

    def test_copied_run_or_incident_is_not_verified(self):
        for params in ({"expected_run_id":"RUN-B"},{"expected_incident_id":"INC-B"}):
            r=self.read(**params)
            self.assertEqual(r.json()["status"],"UNKNOWN")
            self.hidden(r)
        self.fake.core=("INC-B","INC-B")
        r=self.read()
        self.assertEqual(r.json()["status"],"UNKNOWN")
        self.hidden(r)
    def test_cross_tenant_owner_denied(self):
        self.fake.owners[1]=("run","RUN-A","TEN-B",True)
        r=self.read()
        self.assertEqual(r.status_code,403)
        self.hidden(r)
    def test_missing_glpi_entity_or_unverified_owner(self):
        self.fake.owners.pop()
        r=self.read()
        self.assertEqual(r.json()["status"],"UNKNOWN")
        self.hidden(r)
        self.fake.owners=list(OWNERS)
        self.fake.owners[3]=("glpi_ticket","GLPI-A:123","TEN-A",False)
        r=self.read()
        self.assertEqual(r.json()["status"],"UNKNOWN")
        self.hidden(r)
    def test_stale_conflict_no_ids(self):
        for change,status in (({"observed_at":NOW-timedelta(minutes=10)},"STALE"),
                              ({"known_at":NOW+timedelta(minutes=10)},"CONFLICT"),
                              ({"observed_at":NOW+timedelta(minutes=1),
                                "known_at":NOW+timedelta(minutes=2)},"CONFLICT")):
            self.fake.events=[event(**change)]
            r=self.read()
            self.assertEqual(r.json()["status"],status)
            self.hidden(r)
    def test_tampered_signature_or_forged_provenance_unknown(self):
        row=list(event())
        row[-1]="0"*64
        self.fake.events=[tuple(row)]
        r=self.read()
        self.assertEqual(r.json()["status"],"UNKNOWN")
        self.hidden(r)
        self.fake.events=[event(glpi_ticket_readback_verified=False)]
        r=self.read()
        self.assertEqual(r.json()["status"],"UNKNOWN")
        self.hidden(r)
    def test_orphan_mapping_version_two_is_conflict(self):
        # A signed row cannot invent a missing version-one predecessor.
        # PostgreSQL permits this shape; the read API must fail closed.
        self.fake.events=[event(association_id="XREF-ORPHAN",
                                source_event_id="EVT-ORPHAN",
                                mapping_version=2,
                                supersedes_association_id=None)]
        r=self.read(expected_run_id="RUN-A",expected_incident_id="INC-A")
        self.assertEqual(r.status_code,200,r.text)
        self.assertEqual(r.json()["status"],"CONFLICT")
        self.hidden(r)
        self.assertEqual(len(self.fake.calls),1)

    def test_signed_history_predecessor_cannot_time_travel(self):
        # Both versions are individually HMAC-signed; a valid final row must
        # not hide a future or chronologically inverted predecessor.
        final=dict(association_id="XREF-B",source_event_id="EVT-B",
                   mapping_version=2,supersedes_association_id="XREF-A")
        cases=(
            (event(observed_at=NOW+timedelta(minutes=2),
                   known_at=NOW+timedelta(minutes=3)), "CONFLICT"),
            (event(known_at=NOW-timedelta(seconds=5)), "CONFLICT"),
            (event(known_at=None), "UNKNOWN"),
        )
        for first,status in cases:
            with self.subTest(status=status,first=first):
                self.fake.events=[first,event(**final)]
                r=self.read(expected_run_id="RUN-A")
                self.assertEqual(r.status_code,200,r.text)
                self.assertEqual(r.json()["status"],status)
                self.hidden(r)
                self.assertEqual(self.fake.calls[-1][0].count("itsm_xref_events"),1)
                self.assertNotIn("from aiops.runs",self.fake.calls[-1][0])
        # No historical event can have a later known_at than its successor.
        self.assertTrue(all("from aiops.runs" not in sql for sql,_ in self.fake.calls))

    def test_signed_supersession_observation_cannot_go_backwards(self):
        # Both rows have valid HMAC, recent observed_at and increasing known_at.
        # A backdated successor must not silently become an authoritative link.
        self.fake.events=[
            event(observed_at=NOW-timedelta(seconds=20),
                  known_at=NOW-timedelta(seconds=15)),
            event(association_id="XREF-B",source_event_id="EVT-B",
                  mapping_version=2,supersedes_association_id="XREF-A",
                  observed_at=NOW-timedelta(seconds=25),
                  known_at=NOW-timedelta(seconds=5))]
        r=self.read(expected_run_id="RUN-A",expected_incident_id="INC-A")
        self.assertEqual(r.status_code,200,r.text)
        self.assertEqual(r.json()["status"],"CONFLICT")
        self.hidden(r)
        self.assertEqual(len(self.fake.calls),1)

    def test_duplicate_and_conflicting_history(self):
        self.fake.events=[event(),event()]
        r=self.read()
        self.assertEqual(r.json()["status"],"CONFLICT")
        self.hidden(r)
        self.fake.events=[event(),event(association_id="XREF-B",source_event_id="EVT-B",
                          mapping_version=2,supersedes_association_id=None)]
        r=self.read()
        self.assertEqual(r.json()["status"],"CONFLICT")
        self.hidden(r)
    def test_owner_provenance_and_bitemporal_integrity_fail_closed(self):
        owner=OWNERS[3]
        cases=(
            (owner+("",NOW-timedelta(seconds=30),NOW-timedelta(seconds=10)),"UNKNOWN"),
            (owner+("EVT-OWNER",NOW+timedelta(minutes=2),NOW+timedelta(minutes=3)),"CONFLICT"),
            (owner+("EVT-OWNER",NOW-timedelta(seconds=1),NOW-timedelta(seconds=10)),"CONFLICT"),
            (owner+("EVT-OWNER",NOW-timedelta(seconds=30),None),"UNKNOWN"),
        )
        for record,status in cases:
            with self.subTest(status=status,record=record):
                self.fake.owners[3]=record
                r=self.read()
                self.assertEqual(r.status_code,200,r.text)
                self.assertEqual(r.json()["status"],status)
                self.hidden(r)
        self.fake.owners[3]=owner
        self.assertEqual(self.read().json()["status"],"VERIFIED")

    def test_supersession_and_revocation(self):
        newer=dict(association_id="XREF-B",source_event_id="EVT-B",mapping_version=2,
                   supersedes_association_id="XREF-A")
        self.fake.events=[event(),event(**newer)]
        self.assertEqual(self.read().json()["status"],"VERIFIED")
        self.fake.events=[event(),event(event_type="REVOKED",**newer)]
        r=self.read()
        self.assertEqual(r.json()["status"],"UNKNOWN")
        self.hidden(r)

if __name__=="__main__": unittest.main()


# Core-owned test bridge: shared Quality invokes this existing suite by name.
# Do not edit the architect-owned workflow for a focused actor ACL addition.
def load_tests(loader, tests, pattern):
    from test_core_actor_resource_authz import ActorDelegationTests
    tests.addTests(loader.loadTestsFromTestCase(ActorDelegationTests))
    from test_core_hitl_reject_delivery import RejectDeliveryTests
    tests.addTests(loader.loadTestsFromTestCase(RejectDeliveryTests))
    from test_core_actor_native_authority import NativeActorRightsTests
    tests.addTests(loader.loadTestsFromTestCase(NativeActorRightsTests))
    from test_core_actor_replay_fence import ActorReplayFenceTests
    tests.addTests(loader.loadTestsFromTestCase(ActorReplayFenceTests))
    from test_core_actor_disposable_sources import DisposableHumanAuthorityTests
    tests.addTests(loader.loadTestsFromTestCase(DisposableHumanAuthorityTests))
    from test_core_actor_native_tls_sources import DisposableNativeTLSAuthorityTests
    tests.addTests(loader.loadTestsFromTestCase(DisposableNativeTLSAuthorityTests))
    from test_core_actor_run_event_source import CoreActorSourceBindingTests
    tests.addTests(loader.loadTestsFromTestCase(CoreActorSourceBindingTests))
    return tests
