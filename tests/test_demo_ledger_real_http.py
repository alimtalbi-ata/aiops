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
EVIDENCE = "EVD-CI-LEDGER-SAN"
PRIVATE = "CI-PRIVATE-PROMPT-MUST-NOT-LEAK"


class RealLedgerHttpQualification(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Isolated PostgreSQL container is destroyed after the job; never mutate
        # an external service or reuse runtime IDs from the ACME scenario fixture.
        with psycopg.connect(DSN) as conn:
            for rid, mode in ((RUN, "DEMO"), (LIVE, "LIVE"), (UNSOURCED, "DEMO")):
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
        self.assertIs(body["tenant_acl_qualified"], False)
        self.assertIs(body["runtime_attested"], False)
        self.assertEqual(body["analyses"][0]["evidence_ids"], [EVIDENCE])
        self.assertEqual(body["critiques"][0]["analysis_id"], "ANL-CI-LEDGER")
        self.assertIs(body["critiques"][0]["claim_checks"][0]["supported"], False)
        self.assertEqual(response.headers["cache-control"], "no-store")
        for secret in (PRIVATE, VIEWER, INTERNAL, "private_prompt"):
            self.assertNotIn(secret, response.text)

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
        for secret in (INTERNAL, VIEWER, PRIVATE, "synthetic_only", "payload"):
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


if __name__ == "__main__":
    unittest.main()
