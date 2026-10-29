"""Real ephemeral Core/PostgreSQL and Portal HTTP qualification for Demo Studio ledger.

No mocks, no production services, no NGX, no tenant ACL assertion. This test
runs only after disposable PostgreSQL migrations in quality.yml.
"""
import hashlib
import json
import os
import unittest

import psycopg
import requests
from psycopg.types.json import Jsonb

CORE = "http://127.0.0.1:1810"
PORTAL = "http://127.0.0.1:1877"
BAD_PORTAL = "http://127.0.0.1:1878"
INTERNAL = os.environ["AIOPS_INTERNAL_TOKEN"]
VIEWER = os.environ["AIOPS_PORTAL_READ_TOKEN"]
DSN = os.environ["DATABASE_URL"]
RUN = "RUN-CI-LEDGER-DEMO"
LIVE = "RUN-CI-LEDGER-LIVE"
UNSOURCED = "RUN-CI-LEDGER-UNSOURCED"
NO_EVENT = "RUN-CI-LEDGER-NO-EVENT"
EVIDENCE = "EVD-CI-LEDGER-SAN"
PRIVATE = "CI-PRIVATE-PROMPT-MUST-NOT-LEAK"


class RealLedgerHttpQualification(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Isolated PostgreSQL container is destroyed after the job; never mutate
        # an external service or reuse runtime IDs from the ACME scenario fixture.
        with psycopg.connect(DSN) as conn:
            for rid, mode in ((RUN, "DEMO"), (LIVE, "LIVE"), (UNSOURCED, "DEMO"), (NO_EVENT, "DEMO")):
                conn.execute(
                    "insert into aiops.runs(run_id,mode,scenario_id,status,idempotency_key) "
                    "values(%s,%s,'CI-LEDGER-ISOLATED','CREATED',%s)",
                    (rid, mode, "ci-ledger-" + rid),
                )
            conn.execute(
                "insert into aiops.evidence(evidence_id,source,claim,confidence,provenance,"
                "payload_hash,payload) values(%s,'CI_SYNTHETIC_SAN','Synthetic SAN CRC',"
                "0.7,%s,%s,%s)",
                (EVIDENCE, Jsonb({"synthetic": True, "observed": False, "run_id": RUN}),
                 hashlib.sha256(b"CI synthetic SAN evidence").hexdigest(),
                 Jsonb({"synthetic_only": True})),
            )
            # A genuine Run event is required: a ledger ID alone is not a source.
            conn.execute(
                "insert into aiops.run_events(event_id,run_id,sequence,stage,event_type,"
                "status,evidence_ids,payload) values(%s,%s,1,'OBSERVE','CI_SYNTHETIC',"
                "'PASS',%s,%s)",
                ("EVT-CI-LEDGER-SAN", RUN, Jsonb([EVIDENCE]),
                 Jsonb({"synthetic": True})),
            )
            # An event on a different Run must not authorize this evidence.
            conn.execute(
                "insert into aiops.run_events(event_id,run_id,sequence,stage,event_type,"
                "status,evidence_ids,payload) values(%s,%s,1,'OBSERVE','CI_CROSS_RUN',"
                "'PASS',%s,%s)",
                ("EVT-CI-LEDGER-CROSS", UNSOURCED, Jsonb([EVIDENCE]),
                 Jsonb({"synthetic": True})),
            )
            ids = [EVIDENCE]
            digest = hashlib.sha256(json.dumps(ids, separators=(",", ":")).encode()).hexdigest()
            conn.execute(
                "insert into aiops.analysis_records(analysis_id,run_id,idempotency_key,"
                "revision,contract_version,provider,model,prompt_version,evidence_ids,"
                "evidence_set_hash,output,confidence,status) "
                "values('ANL-CI-LEDGER',%s,'ci-ledger-analysis',1,'2.0',"
                "'CI_ONLY','CI_NOT_LLM','ci',%s,%s,%s,0.7,'VALID')",
                (RUN, Jsonb(ids), digest, Jsonb({"private_prompt": PRIVATE})),
            )
            conn.execute(
                "insert into aiops.critique_records(critique_id,idempotency_key,analysis_id,"
                "run_id,contract_version,provider,model,validated,issues,evidence_ids,"
                "output,diagnostic_confidence) "
                "values('CRT-CI-LEDGER','ci-ledger-critique','ANL-CI-LEDGER',%s,"
                "'2.0','CI_ONLY','CI_NOT_LLM',false,'[]'::jsonb,%s,%s,0.4)",
                (RUN, Jsonb(ids), Jsonb({"claim_checks": [
                    {"claim": "Synthetic SAN CRC", "supported": False,
                     "supporting_evidence_ids": []}]})),
            )

            # Fully consistent ledger/evidence rows without a Run event must
            # not become a sourced claim through the Portal.
            no_event_evidence = "EVD-CI-LEDGER-NO-EVENT"
            conn.execute(
                "insert into aiops.evidence(evidence_id,source,claim,confidence,provenance,"
                "payload_hash,payload) values(%s,'CI_SYNTHETIC_SAN','No event',"
                "0.5,%s,%s,'{}'::jsonb)",
                (no_event_evidence, Jsonb({"synthetic": True, "observed": False,
                                          "run_id": NO_EVENT}),
                 hashlib.sha256(b"ci no event").hexdigest()),
            )
            no_event_ids = [no_event_evidence]
            no_event_hash = hashlib.sha256(json.dumps(
                no_event_ids, separators=(",", ":")).encode()).hexdigest()
            conn.execute(
                "insert into aiops.analysis_records(analysis_id,run_id,idempotency_key,"
                "revision,contract_version,provider,model,prompt_version,evidence_ids,"
                "evidence_set_hash,output,confidence,status) values("
                "'ANL-CI-NO-EVENT',%s,'ci-ledger-no-event-analysis',1,'2.0',"
                "'CI_ONLY','CI_NOT_LLM','ci',%s,%s,'{}'::jsonb,0.5,'VALID')",
                (NO_EVENT, Jsonb(no_event_ids), no_event_hash),
            )
            conn.execute(
                "insert into aiops.critique_records(critique_id,idempotency_key,"
                "analysis_id,run_id,contract_version,provider,model,validated,issues,"
                "evidence_ids,output,diagnostic_confidence) values("
                "'CRT-CI-NO-EVENT','ci-ledger-no-event-critique','ANL-CI-NO-EVENT',"
                "%s,'2.0','CI_ONLY','CI_NOT_LLM',true,'[]'::jsonb,%s,%s,0.4)",
                (NO_EVENT, Jsonb(no_event_ids),
                 Jsonb({"claim_checks": [{"claim": "No event synthetic claim",
                                         "supported": True,
                                         "supporting_evidence_ids": no_event_ids}]})),
            )

            # The DB contains a genuine immutable Critique row with a forged
            # supporting ID; the Portal must not display it as sourced.
            conn.execute(
                "insert into aiops.analysis_records(analysis_id,run_id,idempotency_key,"
                "revision,contract_version,provider,model,prompt_version,evidence_ids,"
                "evidence_set_hash,output,confidence,status) "
                "values('ANL-CI-UNSOURCED',%s,'ci-ledger-unsourced-analysis',1,'2.0',"
                "'CI_ONLY','CI_NOT_LLM','ci',%s,%s,%s,0.7,'VALID')",
                (UNSOURCED, Jsonb([EVIDENCE]), digest, Jsonb({"synthetic_only": True})),
            )
            conn.execute(
                "insert into aiops.critique_records(critique_id,idempotency_key,analysis_id,"
                "run_id,contract_version,provider,model,validated,issues,evidence_ids,"
                "output,diagnostic_confidence) "
                "values('CRT-CI-UNSOURCED','ci-ledger-unsourced-critique',"
                "'ANL-CI-UNSOURCED',%s,'2.0','CI_ONLY','CI_NOT_LLM',true,"
                "'[]'::jsonb,%s,%s,0.4)",
                (UNSOURCED, Jsonb([EVIDENCE]), Jsonb({"claim_checks": [{
                    "claim": "Payments outage proven", "supported": True,
                    "supporting_evidence_ids": ["EVD-CI-NOT-IN-ANALYSIS"],
                }]})),
            )

    def read(self, base, rid=RUN, token=VIEWER):
        headers = {} if token is None else {"Authorization": "Bearer " + token}
        return requests.get(base + "/api/demo-studio/runs/" + rid + "/ai-ledger",
                            headers=headers, timeout=5, allow_redirects=False)

    def test_core_real_auth_401_and_ledger_source(self):
        url = CORE + "/api/runs/" + RUN + "/ai-ledger"
        for headers in ({}, {"Authorization": "Bearer invalid"}):
            response = requests.get(url, headers=headers, timeout=5, allow_redirects=False)
            self.assertEqual(response.status_code, 401)
        response = requests.get(url, headers={"Authorization": "Bearer " + INTERNAL},
                                timeout=5, allow_redirects=False)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["analyses"][0]["evidence_ids"], [EVIDENCE])
        self.assertEqual(response.json()["analyses"][0]["output"]["private_prompt"], PRIVATE)

    def test_portal_auth_before_read_and_no_token_or_private_data(self):
        for token in (None, "invalid"):
            response = self.read(PORTAL, token=token)
            self.assertEqual(response.status_code, 401)
            self.assertEqual(response.headers["cache-control"], "no-store")
            self.assertNotIn(RUN, response.text)
        response = self.read(PORTAL)
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["schema"], "aiops.demo-ledger-read.v1")
        self.assertEqual(body["run_id"], RUN)
        self.assertEqual(body["mode"], "DEMO")
        self.assertEqual(body["classification"], "DEMO_CORE_RECORDED_NOT_LIVE")
        self.assertEqual(body["evidence_classification"], "SYNTHETIC_ONLY")
        self.assertIs(body["event_link_verified"], True)
        self.assertEqual([ref["evidence_id"] for ref in body["evidence_refs"]], [EVIDENCE])
        self.assertEqual(body["evidence_refs"][0]["source"], "CI_SYNTHETIC_SAN")
        self.assertIs(body["tenant_acl_qualified"], False)
        self.assertIs(body["runtime_attested"], False)
        self.assertEqual(body["analyses"][0]["evidence_ids"], [EVIDENCE])
        self.assertEqual(body["critiques"][0]["analysis_id"], "ANL-CI-LEDGER")
        self.assertIs(body["critiques"][0]["claim_checks"][0]["supported"], False)
        self.assertEqual(response.headers["cache-control"], "no-store")
        for secret in (PRIVATE, VIEWER, INTERNAL, "private_prompt"):
            self.assertNotIn(secret, response.text)

    def test_real_portal_malformed_viewer_bearer_is_401(self):
        # Real HTTP parser + Portal; no Core/DB fixture mutation.
        # HTTP parsers may normalize trailing OWS before application auth.
        # Whitespace rejection is covered at the application boundary in unit tests.
        for credential in ("café", "x" * 4096):
            with self.subTest(credential_length=len(credential)):
                denied = requests.get(
                    PORTAL + "/api/demo-studio/runs/" + RUN + "/ai-ledger",
                    headers={"Authorization": "Bearer " + credential},
                    timeout=5, allow_redirects=False)
                self.assertEqual(denied.status_code, 401, denied.text)
                self.assertEqual(denied.json(),
                                 {"status": "UNKNOWN", "reason": "unauthorized"})
                self.assertEqual(denied.headers["cache-control"], "no-store")
                for secret in (RUN, VIEWER, INTERNAL, PRIVATE):
                    self.assertNotIn(secret, denied.text)

    def test_live_and_missing_sources_fail_closed(self):
        for rid in (LIVE, "RUN-CI-LEDGER-MISSING"):
            response = self.read(PORTAL, rid=rid)
            self.assertEqual(response.status_code, 503)
            self.assertEqual(response.json()["status"], "UNKNOWN")
            self.assertEqual(response.headers["cache-control"], "no-store")
            self.assertNotIn(rid, response.text)

    def test_persisted_unsourced_claim_fails_closed(self):
        # Real Core and PostgreSQL contain the forged claim; no mock.
        core = requests.get(CORE + "/api/runs/" + UNSOURCED + "/ai-ledger",
                            headers={"Authorization": "Bearer " + INTERNAL},
                            timeout=5, allow_redirects=False)
        self.assertEqual(core.status_code, 200)
        self.assertEqual(core.json()["critiques"][0]["output"]["claim_checks"][0]
                         ["supporting_evidence_ids"], ["EVD-CI-NOT-IN-ANALYSIS"])
        denied = self.read(PORTAL, rid=UNSOURCED)
        self.assertEqual(denied.status_code, 503)
        self.assertEqual(denied.json(), {"status": "UNKNOWN",
                                         "reason": "ledger_unavailable"})
        self.assertEqual(denied.headers["cache-control"], "no-store")
        for private in (UNSOURCED, "EVD-CI-NOT-IN-ANALYSIS", INTERNAL, VIEWER):
            self.assertNotIn(private, denied.text)

    def test_real_ledger_without_run_event_is_unknown(self):
        core_ledger = requests.get(
            CORE + "/api/runs/" + NO_EVENT + "/ai-ledger",
            headers={"Authorization": "Bearer " + INTERNAL},
            timeout=5, allow_redirects=False)
        self.assertEqual(core_ledger.status_code, 200, core_ledger.text)
        self.assertTrue(core_ledger.json()["critiques"][0]["output"]
                        ["claim_checks"][0]["supported"])
        denied = self.read(PORTAL, rid=NO_EVENT)
        self.assertEqual(denied.status_code, 503, denied.text)
        self.assertEqual(denied.json(), {"status": "UNKNOWN",
                                         "reason": "ledger_unavailable"})
        self.assertNotIn(NO_EVENT, denied.text)
        self.assertNotIn("EVD-CI-LEDGER-NO-EVENT", denied.text)
        self.assertEqual(denied.headers["cache-control"], "no-store")

    def test_future_dated_evidence_refused_by_real_core_and_portal(self):
        # Evidence rows are append-only: seed a separate genuine future-dated
        # Run/Evidence/Analysis/Critique in ephemeral PostgreSQL, never UPDATE.
        future_run = "RUN-CI-LEDGER-FUTURE"
        future_evidence = "EVD-CI-LEDGER-FUTURE"
        ids = [future_evidence]
        digest = hashlib.sha256(json.dumps(ids, separators=(",", ":")).encode()).hexdigest()
        with psycopg.connect(DSN) as conn:
            conn.execute(
                "insert into aiops.runs(run_id,mode,scenario_id,status,idempotency_key) "
                "values(%s,'DEMO','CI-LEDGER-ISOLATED','CREATED',%s)",
                (future_run, "ci-ledger-future-run"),
            )
            conn.execute(
                "insert into aiops.evidence(evidence_id,source,claim,confidence,"
                "provenance,payload_hash,payload,known_at) values("
                "%s,'CI_SYNTHETIC_SAN','Future synthetic claim',0.5,%s,%s,"
                "'{}'::jsonb,now() + interval '1 day')",
                (future_evidence, Jsonb({"synthetic": True, "observed": False,
                                         "run_id": future_run}),
                 hashlib.sha256(b"ci-future-evidence").hexdigest()),
            )
            conn.execute(
                "insert into aiops.run_events(event_id,run_id,sequence,stage,event_type,"
                "status,evidence_ids,payload) values(%s,%s,1,'OBSERVE','CI_FUTURE',"
                "'PASS',%s,'{}'::jsonb)",
                ("EVT-CI-LEDGER-FUTURE", future_run, Jsonb(ids)),
            )
            conn.execute(
                "insert into aiops.analysis_records(analysis_id,run_id,idempotency_key,"
                "revision,contract_version,provider,model,prompt_version,evidence_ids,"
                "evidence_set_hash,output,confidence,status) values("
                "'ANL-CI-FUTURE',%s,'ci-ledger-future-analysis',1,'2.0',"
                "'CI_ONLY','CI_NOT_LLM','ci',%s,%s,'{}'::jsonb,0.5,'VALID')",
                (future_run, Jsonb(ids), digest),
            )
            conn.execute(
                "insert into aiops.critique_records(critique_id,idempotency_key,"
                "analysis_id,run_id,contract_version,provider,model,validated,issues,"
                "evidence_ids,output,diagnostic_confidence) values("
                "'CRT-CI-FUTURE','ci-ledger-future-critique','ANL-CI-FUTURE',"
                "%s,'2.0','CI_ONLY','CI_NOT_LLM',true,'[]'::jsonb,%s,%s,0.4)",
                (future_run, Jsonb(ids), Jsonb({"claim_checks": [
                    {"claim": "Future synthetic claim", "supported": True,
                     "supporting_evidence_ids": ids}]})),
            )
        auth = {"Authorization": "Bearer " + INTERNAL}
        ledger = requests.get(CORE + "/api/runs/" + future_run + "/ai-ledger",
                              headers=auth, timeout=5, allow_redirects=False)
        self.assertEqual(ledger.status_code, 200, ledger.text)
        core = requests.get(
            CORE + "/api/noc/runs/" + future_run + "/evidence-refs",
            headers=auth, timeout=5, allow_redirects=False,
        )
        self.assertEqual(core.status_code, 503, core.text)
        self.assertNotIn(future_evidence, core.text)
        portal = self.read(PORTAL, rid=future_run)
        self.assertEqual(portal.status_code, 503, portal.text)
        self.assertEqual(portal.json(), {"status": "UNKNOWN",
                                         "reason": "ledger_unavailable"})
        self.assertEqual(portal.headers["cache-control"], "no-store")
        for private in (future_run, future_evidence, INTERNAL, VIEWER):
            self.assertNotIn(private, portal.text)

    def test_real_upstream_401_becomes_unknown_without_leak(self):
        # Second real Portal process deliberately has a different CI-only
        # internal token; Core must reject its request, not the viewer token.
        response = self.read(BAD_PORTAL)
        self.assertEqual(response.status_code, 503, response.text)
        self.assertEqual(response.json(), {"status": "UNKNOWN",
                                           "reason": "ledger_unavailable"})
        self.assertEqual(response.headers["cache-control"], "no-store")
        for secret in (VIEWER, INTERNAL, "ci-ledger-wrong"):
            self.assertNotIn(secret, response.text)

    def test_core_synthetic_evidence_refs_require_internal_auth_and_event(self):
        url = CORE + "/api/noc/runs/" + RUN + "/evidence-refs"
        for headers in ({}, {"Authorization": "Bearer wrong"}):
            denied = requests.get(url, headers=headers, timeout=5,
                                  allow_redirects=False)
            self.assertEqual(denied.status_code, 401)
        allowed = requests.get(url, headers={"Authorization": "Bearer " + INTERNAL},
                               timeout=5, allow_redirects=False)
        self.assertEqual(allowed.status_code, 200, allowed.text)
        data = allowed.json()
        self.assertEqual(data["schema"], "aiops.core-demo-evidence-refs.v1")
        self.assertEqual(data["run_id"], RUN)
        self.assertEqual(data["classification"], "SYNTHETIC_ONLY")
        self.assertIs(data["event_link_verified"], True)
        self.assertIs(data["tenant_acl_qualified"], False)
        self.assertIs(data["runtime_attested"], False)
        self.assertEqual([item["evidence_id"] for item in data["items"]], [EVIDENCE])
        self.assertEqual(data["items"][0]["source"], "CI_SYNTHETIC_SAN")
        self.assertEqual(len(data["items"][0]["payload_sha256"]), 64)
        self.assertTrue(data["items"][0]["known_at"])
        for secret in (INTERNAL, VIEWER, PRIVATE, "synthetic_only", '"payload":'):
            self.assertNotIn(secret, allowed.text)

    def test_core_evidence_refs_fail_closed_for_live_cross_run_and_absent(self):
        headers = {"Authorization": "Bearer " + INTERNAL}
        for rid in (LIVE, UNSOURCED, "RUN-CI-LEDGER-MISSING"):
            with self.subTest(rid=rid):
                denied = requests.get(
                    CORE + "/api/noc/runs/" + rid + "/evidence-refs",
                    headers=headers, timeout=5, allow_redirects=False,
                )
                self.assertEqual(denied.status_code, 503, denied.text)
                self.assertNotIn(rid, denied.text)
                self.assertNotIn(EVIDENCE, denied.text)

    def test_core_evidence_refs_refuse_tenant_metadata(self):
        tenant_run = "RUN-CI-LEDGER-TENANT"
        tenant_evidence = "EVD-CI-LEDGER-TENANT"
        with psycopg.connect(DSN) as conn:
            conn.execute(
                "insert into aiops.runs(run_id,mode,scenario_id,status,idempotency_key)"
                " values(%s,'DEMO','CI-LEDGER-ISOLATED','CREATED',%s)",
                (tenant_run, "ci-ledger-tenant-run"),
            )
            conn.execute(
                "insert into aiops.evidence(evidence_id,source,claim,confidence,provenance,"
                "payload_hash,payload) values(%s,'CI_SYNTHETIC_SAN','tenant-only',"
                "0.5,%s,%s,%s)",
                (tenant_evidence,
                 Jsonb({"synthetic": True, "observed": False,
                        "run_id": tenant_run, "ownerTenantId": "TENANT-B"}),
                 hashlib.sha256(b"tenant-only-ci-evidence").hexdigest(),
                 Jsonb({"synthetic_only": True})),
            )
            ids = [tenant_evidence]
            digest = hashlib.sha256(json.dumps(ids, separators=(",", ":")).encode()).hexdigest()
            conn.execute(
                "insert into aiops.analysis_records(analysis_id,run_id,idempotency_key,"
                "revision,contract_version,provider,model,prompt_version,evidence_ids,"
                "evidence_set_hash,output,confidence,status) values(%s,%s,%s,1,'2.0',"
                "'CI_ONLY','CI_NOT_LLM','ci',%s,%s,'{}'::jsonb,0.5,'VALID')",
                ("ANL-CI-LEDGER-TENANT", tenant_run, "ci-ledger-tenant-analysis",
                 Jsonb(ids), digest),
            )
            conn.execute(
                "insert into aiops.critique_records(critique_id,idempotency_key,"
                "analysis_id,run_id,contract_version,provider,model,validated,issues,"
                "evidence_ids,output,diagnostic_confidence) values(%s,%s,%s,%s,'2.0',"
                "'CI_ONLY','CI_NOT_LLM',false,'[]'::jsonb,%s,'{}'::jsonb,0.4)",
                ("CRT-CI-LEDGER-TENANT", "ci-ledger-tenant-critique",
                 "ANL-CI-LEDGER-TENANT", tenant_run, Jsonb(ids)),
            )
            conn.execute(
                "insert into aiops.run_events(event_id,run_id,sequence,stage,event_type,"
                "status,evidence_ids,payload) values(%s,%s,1,'OBSERVE','CI_TENANT',"
                "'PASS',%s,'{}'::jsonb)",
                ("EVT-CI-LEDGER-TENANT", tenant_run, Jsonb(ids)),
            )
        denied = requests.get(
            CORE + "/api/noc/runs/" + tenant_run + "/evidence-refs",
            headers={"Authorization": "Bearer " + INTERNAL},
            timeout=5, allow_redirects=False,
        )
        self.assertEqual(denied.status_code, 503, denied.text)
        self.assertNotIn("TENANT-B", denied.text)
        self.assertNotIn(tenant_evidence, denied.text)


    def test_real_policy_live_allow_fails_closed(self):
        # Policy's real evaluate() emits ALLOW only for LIVE. A persisted
        # synthetic Run with ALLOW must never be presented as a DEMO success.
        before = self.read(PORTAL, rid=RUN)
        self.assertEqual(before.status_code, 200, before.text)
        with psycopg.connect(DSN) as conn:
            conn.execute(
                "insert into aiops.policy_decisions(policy_decision_id,run_id,"
                "analysis_id,critique_id,policy_version,input_hash,decision,state)"
                " values('POL-CI-LEDGER-LIVE-ALLOW',%s,'ANL-CI-LEDGER',"
                "'CRT-CI-LEDGER','2.1.0',%s,'ALLOW','PASS')",
                (RUN, hashlib.sha256(b"ci-policy-forged-live-allow").hexdigest()),
            )
        core = requests.get(
            CORE + "/api/runs/" + RUN + "/ai-ledger",
            headers={"Authorization": "Bearer " + INTERNAL},
            timeout=5, allow_redirects=False,
        )
        self.assertEqual(core.status_code, 200, core.text)
        self.assertIn("ALLOW", [x["decision"] for x in core.json()["policy_decisions"]])
        denied = self.read(PORTAL, rid=RUN)
        self.assertEqual(denied.status_code, 503, denied.text)
        self.assertEqual(denied.json(), {"status": "UNKNOWN",
                                         "reason": "ledger_unavailable"})
        self.assertEqual(denied.headers["cache-control"], "no-store")
        for private in (RUN, "POL-CI-LEDGER-LIVE-ALLOW", INTERNAL, VIEWER):
            self.assertNotIn(private, denied.text)

    def test_real_policy_foreign_run_links_fail_closed(self):
        # Actual PostgreSQL foreign keys permit a Policy decision attached to
        # one Run to cite Analysis/Critique IDs from another. The Portal must
        # reject the resulting Core ledger, even with valid synthetic Evidence.
        rid = "RUN-CI-LEDGER-POLICY-CROSS"
        evid = "EVD-CI-LEDGER-POLICY-CROSS"
        aid = "ANL-CI-LEDGER-POLICY-CROSS"
        cid = "CRT-CI-LEDGER-POLICY-CROSS"
        ids = [evid]
        digest = hashlib.sha256(json.dumps(ids, separators=(",", ":")).encode()).hexdigest()
        with psycopg.connect(DSN) as conn:
            conn.execute(
                "insert into aiops.runs(run_id,mode,scenario_id,status,idempotency_key) "
                "values(%s,'DEMO','CI-LEDGER-ISOLATED','CREATED',%s)",
                (rid, "ci-ledger-policy-cross-run"),
            )
            conn.execute(
                "insert into aiops.evidence(evidence_id,source,claim,confidence,"
                "provenance,payload_hash,payload) values(%s,'CI_SYNTHETIC_SAN',"
                "'Policy linkage synthetic',0.5,%s,%s,'{}'::jsonb)",
                (evid, Jsonb({"synthetic": True, "observed": False, "run_id": rid}),
                 hashlib.sha256(b"ci-policy-cross-evidence").hexdigest()),
            )
            conn.execute(
                "insert into aiops.run_events(event_id,run_id,sequence,stage,event_type,"
                "status,evidence_ids,payload) values(%s,%s,1,'OBSERVE','CI_SYNTHETIC',"
                "'PASS',%s,'{}'::jsonb)",
                ("EVT-CI-LEDGER-POLICY-CROSS", rid, Jsonb(ids)),
            )
            conn.execute(
                "insert into aiops.analysis_records(analysis_id,run_id,idempotency_key,"
                "revision,contract_version,provider,model,prompt_version,evidence_ids,"
                "evidence_set_hash,output,confidence,status) values(%s,%s,%s,1,'2.0',"
                "'CI_ONLY','CI_NOT_LLM','ci',%s,%s,'{}'::jsonb,0.5,'VALID')",
                (aid, rid, "ci-ledger-policy-cross-analysis", Jsonb(ids), digest),
            )
            conn.execute(
                "insert into aiops.critique_records(critique_id,idempotency_key,"
                "analysis_id,run_id,contract_version,provider,model,validated,issues,"
                "evidence_ids,output,diagnostic_confidence) values("
                "%s,%s,%s,%s,'2.0','CI_ONLY','CI_NOT_LLM',false,'[]'::jsonb,"
                "%s,%s,0.4)",
                (cid, "ci-ledger-policy-cross-critique", aid, rid, Jsonb(ids),
                 Jsonb({"claim_checks": []})),
            )
            conn.execute(
                "insert into aiops.policy_decisions(policy_decision_id,run_id,"
                "analysis_id,critique_id,policy_version,input_hash,decision,state)"
                " values('POL-CI-LEDGER-LOCAL',%s,%s,%s,'2.1.0',%s,'SIMULATE','PASS')",
                (rid, aid, cid, hashlib.sha256(b"ci-policy-local").hexdigest()),
            )
        # This proves only a persisted synthetic Policy record, not execution.
        positive = self.read(PORTAL, rid=rid)
        self.assertEqual(positive.status_code, 200, positive.text)
        self.assertEqual(positive.json()["policy_decisions"][0]["decision"], "SIMULATE")
        with psycopg.connect(DSN) as conn:
            conn.execute(
                "insert into aiops.policy_decisions(policy_decision_id,run_id,"
                "analysis_id,critique_id,policy_version,input_hash,decision,state)"
                " values('POL-CI-LEDGER-FOREIGN',%s,'ANL-CI-LEDGER',"
                "'CRT-CI-LEDGER','2.1.0',%s,'SIMULATE','PASS')",
                (rid, hashlib.sha256(b"ci-policy-foreign").hexdigest()),
            )
        core = requests.get(CORE + "/api/runs/" + rid + "/ai-ledger",
                            headers={"Authorization": "Bearer " + INTERNAL},
                            timeout=5, allow_redirects=False)
        self.assertEqual(core.status_code, 200, core.text)
        self.assertEqual(len(core.json()["policy_decisions"]), 2)
        denied = self.read(PORTAL, rid=rid)
        self.assertEqual(denied.status_code, 503, denied.text)
        self.assertEqual(denied.json(), {"status": "UNKNOWN",
                                         "reason": "ledger_unavailable"})
        self.assertEqual(denied.headers["cache-control"], "no-store")
        for private in (rid, "POL-CI-LEDGER-FOREIGN", INTERNAL, VIEWER):
            self.assertNotIn(private, denied.text)


if __name__ == "__main__":
    unittest.main()
