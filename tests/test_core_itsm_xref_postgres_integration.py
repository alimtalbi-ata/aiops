"""Real Core HTTP + disposable PostgreSQL 16. All source records are CI SYNTHETIC."""
import os, unittest, hashlib, hmac, json
from datetime import datetime, timezone, timedelta
import psycopg, requests
from core.itsm_xref import _COLUMNS, _payload, _owner_proof_payload

BASE="http://127.0.0.1:1810"
PATH="/api/tenants/{tenant}/itsm/glpi/{instance}/tickets/{ticket}/xref"

@unittest.skipUnless(os.getenv("AIOPS_XREF_CI_DISPOSABLE")=="1","disposable CI only")
class XrefPostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.url=os.environ["DATABASE_URL"]
        if "127.0.0.1:5432/" not in cls.url: raise RuntimeError("Refusing non-disposable DB")
        cls.key=os.environ["AIOPS_XREF_ATTESTATION_KEY"].encode()
        cls.owner_key=os.environ["AIOPS_XREF_OWNER_ATTESTATION_KEY"].encode()
        cls.proof_path=os.environ["AIOPS_XREF_OWNER_PROOFS_PATH"]
        cls.token_a=os.environ["AIOPS_XREF_CI_TOKEN_A"]
        cls.token_b=os.environ["AIOPS_XREF_CI_TOKEN_B"]
        cls.token_no_perm=os.environ["AIOPS_XREF_CI_TOKEN_NO_PERM"]
        cls.now=datetime.now(timezone.utc)
        with psycopg.connect(cls.url) as c:
            for suffix,tenant,ticket in (("A","TEN-A","123"),("B","TEN-B","456")):
                c.execute("insert into aiops.incidents(incident_id,external_id,title,severity,state,opened_at,source,synthetic) "
                          "values(%s,%s,'CI synthetic','P1','OPEN',now(),'ci',true)",
                          ("INC-XREF-"+suffix,"CI-XREF-"+suffix))
                c.execute("insert into aiops.runs(run_id,incident_id,mode,scenario_id,status,idempotency_key) "
                          "values(%s,%s,'DEMO','CI-XREF','CREATED',%s)",
                          ("RUN-XREF-"+suffix,"INC-XREF-"+suffix,"ci-xref-"+suffix))
                instance="GLPI-"+suffix
                for kind,rid in (("incident","INC-XREF-"+suffix),("run","RUN-XREF-"+suffix),
                                 ("glpi_instance",instance),("glpi_ticket",instance+":"+ticket),
                                 ("glpi_entity",instance+":0")):
                    c.execute("insert into aiops.tenant_resource_ownership "
                              "(resource_kind,resource_id,tenant_id,source_event_id,verified,observed_at,known_at) "
                              "values(%s,%s,%s,%s,true,%s,%s)",
                              (kind,rid,tenant,"EVT-OWNER-"+suffix,cls.now-timedelta(seconds=30),
                               cls.now-timedelta(seconds=10)))
            for ticket in ("789","790","791","792","795","796","797","798"):
                c.execute("insert into aiops.tenant_resource_ownership "
                          "(resource_kind,resource_id,tenant_id,source_event_id,verified,observed_at,known_at) "
                          "values('glpi_ticket',%s,'TEN-A','EVT-OWNER-A',true,%s,%s)",
                          ("GLPI-A:"+ticket,cls.now-timedelta(seconds=30),cls.now-timedelta(seconds=10)))
            cls.insert(c,"123","BASE")
            cls.insert(c,"789","STALE",observed_at=cls.now-timedelta(minutes=11),
                       known_at=cls.now-timedelta(minutes=10))
            cls.insert(c,"790","CONFLICT")
            cls.insert(c,"790","CONFLICT2",mapping_version=2,supersedes_association_id=None)
            cls.insert(c,"791","FOREIGN",incident_id="INC-XREF-B",run_id="RUN-XREF-B")
            cls.insert(c,"792","SUPER1")
            cls.insert(c,"792","SUPER2",mapping_version=2,supersedes_association_id="XREF-SUPER1")
            cls.insert(c,"795","ORPHAN",mapping_version=2,supersedes_association_id=None)
            # Signed, fresh terminal events cannot conceal an invalid predecessor.
            cls.insert(c,"796","FUTURE1",observed_at=cls.now+timedelta(minutes=2),
                       known_at=cls.now+timedelta(minutes=3))
            cls.insert(c,"796","FUTURE2",mapping_version=2,
                       supersedes_association_id="XREF-FUTURE1")
            cls.insert(c,"797","REVERSED1",known_at=cls.now-timedelta(seconds=5))
            cls.insert(c,"797","REVERSED2",mapping_version=2,
                       supersedes_association_id="XREF-REVERSED1")
            cls.insert(c,"798","BACKDATE1",observed_at=cls.now-timedelta(seconds=20),
                       known_at=cls.now-timedelta(seconds=15))
            cls.insert(c,"798","BACKDATE2",mapping_version=2,
                       supersedes_association_id="XREF-BACKDATE1",
                       observed_at=cls.now-timedelta(seconds=25),
                       known_at=cls.now-timedelta(seconds=5))
        cls.write_proofs()

    @classmethod
    def write_proofs(cls):
        with psycopg.connect(cls.url) as c:
            rows=c.execute("select resource_kind,resource_id,tenant_id,verified,"
                           "source_event_id,observed_at,known_at "
                           "from aiops.tenant_resource_ownership").fetchall()
        proofs={kind+"|"+rid:hmac.new(cls.owner_key,_owner_proof_payload(*row),
                                     hashlib.sha256).hexdigest()
                for row in rows for kind,rid in [row[:2]]}
        tmp=cls.proof_path+".tmp"
        with open(tmp,"w",encoding="utf-8") as out:
            json.dump({"schema":"aiops.core-ownership-proof.v1","proofs":proofs},out)
        os.replace(tmp,cls.proof_path)

    @classmethod
    def insert(cls,c,ticket,suffix,**changes):
        e=dict(association_id="XREF-"+suffix,tenant_id="TEN-A",glpi_instance_id="GLPI-A",
               ticket_id=ticket,glpi_entity_id="0",incident_id="INC-XREF-A",run_id="RUN-XREF-A",
               source_event_id="EVT-XREF-"+suffix,mapping_version=1,event_type="VERIFIED",
               actor_id="ci-glpi-adapter",observed_at=cls.now-timedelta(seconds=25),
               known_at=cls.now-timedelta(seconds=15),supersedes_association_id=None,
               verification_method="AUTHENTICATED_ID_READBACK",provenance="AUTHENTICATED_SOURCE_API",
               glpi_ticket_readback_verified=True,core_run_readback_verified=True,
               source_payload_hash=hashlib.sha256(("synthetic-"+suffix).encode()).hexdigest())
        e.update(changes)
        e["attestation_mac"]=hmac.new(cls.key,_payload(e),hashlib.sha256).hexdigest()
        c.execute("insert into aiops.itsm_xref_events ("+",".join(_COLUMNS)+") values("+
                  ",".join(["%s"]*len(_COLUMNS))+")",tuple(e[k] for k in _COLUMNS))

    def read(self,ticket="123",tenant="TEN-A",instance="GLPI-A",token="a",**params):
        tokens={"a":self.token_a,"b":self.token_b,"none":None,
                "bad":"forged","no_perm":self.token_no_perm}
        val=tokens[token]
        headers={} if val is None else {"Authorization":"Bearer "+val}
        return requests.get(BASE+PATH.format(tenant=tenant,instance=instance,ticket=ticket),
                            headers=headers,params=params,timeout=4,allow_redirects=False)
    def hidden(self,r):
        self.assertNotIn("run_id",r.json())
        self.assertNotIn("incident_id",r.json())
        self.assertNotIn("ticket_id",r.json())
        self.assertEqual(r.headers.get("cache-control"),"no-store")

    def test_real_http_synthetic_hmac_without_glpi_source_is_unknown(self):
        r=self.read(expected_run_id="RUN-XREF-A",expected_incident_id="INC-XREF-A")
        self.assertEqual(r.status_code,200,r.text)
        self.assertEqual(r.json()["status"],"UNKNOWN")
        self.hidden(r)  # no authenticated GLPI source in disposable PG fixture
    def test_auth_and_cross_tenant(self):
        for token,code in (("none",401),("bad",401),("b",403),("no_perm",403)):
            with self.subTest(token=token):
                r=self.read(token=token)
                self.assertEqual(r.status_code,code,r.text)
                self.hidden(r)
        r=self.read(ticket="791")
        self.assertEqual(r.status_code,403)
        self.hidden(r)
    def test_stale_evidence_does_not_bypass_real_http_auth(self):
        stale=(self.now-timedelta(minutes=10)).isoformat()
        for token,code in (("none",401),("bad",401),("b",403),("no_perm",403)):
            with self.subTest(token=token):
                r=self.read(token=token,evidence_known_at=stale)
                self.assertEqual(r.status_code,code,r.text)
                self.hidden(r)
        r=self.read(evidence_known_at=stale)
        self.assertEqual(r.status_code,200,r.text)
        self.assertEqual(r.json()["status"],"STALE")
        self.hidden(r)

    def test_no_mapping_copied_run_and_preflight(self):
        r=self.read(ticket="9999")
        self.assertEqual(r.status_code,404)
        self.hidden(r)
        r=self.read(expected_run_id="RUN-XREF-B")
        self.assertEqual(r.json()["status"],"UNKNOWN")
        self.hidden(r)
        r=self.read(evidence_known_at="2026-10-31T12:00:00")
        self.assertEqual(r.status_code,404)
        self.hidden(r)
    def test_stale_conflict_and_supersession(self):
        for ticket,status in (("789","STALE"),("790","CONFLICT")):
            r=self.read(ticket=ticket)
            self.assertEqual(r.json()["status"],status)
            self.hidden(r)
        r=self.read(ticket="792")
        self.assertEqual(r.json()["status"],"UNKNOWN")
        self.hidden(r)  # signed supersession alone is not GLPI authority
    def test_orphan_history_version_two_postgres_is_not_verified(self):
        # Real PG permits a standalone mapping_version=2; Core must reject it.
        r=self.read(ticket="795",expected_run_id="RUN-XREF-A")
        self.assertEqual(r.status_code,200,r.text)
        self.assertEqual(r.json()["status"],"CONFLICT")
        self.hidden(r)

    def test_postgres_signed_history_chronology_fail_closed(self):
        for ticket in ("796","797","798"):
            with self.subTest(ticket=ticket):
                r=self.read(ticket=ticket,expected_run_id="RUN-XREF-A")
                self.assertEqual(r.status_code,200,r.text)
                self.assertEqual(r.json()["status"],"CONFLICT")
                self.hidden(r)

    def test_postgres_owner_source_and_future_timestamp_fail_closed(self):
        # Real disposable PostgreSQL rows, never a production GLPI/DB write.
        with psycopg.connect(self.url) as c:
            for ticket,source_id,observed,known in (
                ("793","EVT-OWNER-FUTURE",self.now+timedelta(minutes=2),
                 self.now+timedelta(minutes=3)),
                ("794","",self.now-timedelta(seconds=30),
                 self.now-timedelta(seconds=10)),
            ):
                c.execute("insert into aiops.tenant_resource_ownership "
                          "(resource_kind,resource_id,tenant_id,source_event_id,verified,observed_at,known_at) "
                          "values('glpi_ticket',%s,'TEN-A',%s,true,%s,%s)",
                          ("GLPI-A:"+ticket,source_id,observed,known))
                self.insert(c,ticket,"OWNER-"+ticket)
        self.write_proofs()
        for ticket,status in (("793","CONFLICT"),("794","UNKNOWN")):
            with self.subTest(ticket=ticket):
                r=self.read(ticket=ticket)
                self.assertEqual(r.status_code,200,r.text)
                self.assertEqual(r.json()["status"],status)
                self.hidden(r)

    def test_owner_proof_missing_or_tampered_never_verifies(self):
        with open(self.proof_path,encoding="utf-8") as fp:
            original=fp.read()
        try:
            with open(self.proof_path,"w",encoding="utf-8") as fp:
                fp.write('{"schema":"aiops.core-ownership-proof.v1","proofs":{}}')
            r=self.read()
            self.assertEqual(r.status_code,200,r.text)
            self.assertEqual(r.json()["status"],"UNKNOWN")
            self.hidden(r)
        finally:
            with open(self.proof_path,"w",encoding="utf-8") as fp:
                fp.write(original)

    def test_postgres_immutability_and_idempotency(self):
        with self.assertRaises(psycopg.Error):
            with psycopg.connect(self.url) as c:
                c.execute("update aiops.itsm_xref_events set run_id='RUN-XREF-B' where association_id='XREF-BASE'")
        with self.assertRaises(psycopg.Error):
            with psycopg.connect(self.url) as c:
                c.execute("delete from aiops.itsm_xref_events where association_id='XREF-BASE'")
        with self.assertRaises(psycopg.Error):
            with psycopg.connect(self.url) as c:
                self.insert(c,"123","BASE")

if __name__=="__main__": unittest.main()
