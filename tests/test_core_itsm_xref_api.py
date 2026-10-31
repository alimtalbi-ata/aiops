"""Adversarial HTTP tests; mocked DB, no GLPI/production requests."""
import os, json, hmac, hashlib, unittest
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from core import itsm_xref as x

NOW=datetime.now(timezone.utc)
TOKEN="ci-service-a"
KEY="ci-only-test-attestation-key-32bytes-long"
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
    def fetchall(self): return self.events if self.kind=="events" else self.owners
    def fetchone(self): return self.core

class XrefHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app=FastAPI()
        app.include_router(x.router)
        cls.client=TestClient(app)
    def setUp(self):
        self.env=patch.dict(os.environ,{"AIOPS_XREF_READ_AUTHZ_JSON":authz(),
                                       "AIOPS_XREF_ATTESTATION_KEY":KEY})
        self.env.start()
        self.fake=FakeDB()
        self.mock=patch.object(x,"db",self.fake.connect)
        self.mock.start()
    def tearDown(self):
        self.mock.stop()
        self.env.stop()
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
