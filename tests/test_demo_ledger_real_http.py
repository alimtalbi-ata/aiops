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
EVIDENCE = "EVD-CI-LEDGER-SAN"
PRIVATE = "CI-PRIVATE-PROMPT-MUST-NOT-LEAK"


class RealLedgerHttpQualification(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Isolated PostgreSQL container is destroyed after the job; never mutate
        # an external service or reuse runtime IDs from the ACME scenario fixture.
        with psycopg.connect(DSN) as conn:
            for rid, mode in ((RUN, "DEMO"), (LIVE, "LIVE")):
                conn.execute(
                    "insert into aiops.runs(run_id,mode,scenario_id,status,idempotency_key) "
                    "values(%s,%s,'CI-LEDGER-ISOLATED','CREATED',%s)",
                    (rid, mode, "ci-ledger-" + rid),
                )
            conn.execute(
                "insert into aiops.evidence(evidence_id,source,claim,confidence,provenance,"
                "payload_hash,payload) values(%s,'CI_SYNTHETIC_SAN','Synthetic SAN CRC',"
                "0.7,%s,%s,%s)",
                (EVIDENCE, Jsonb({"synthetic": True, "observed": False}),
                 hashlib.sha256(b"CI synthetic SAN evidence").hexdigest(),
                 Jsonb({"synthetic_only": True})),
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


if __name__ == "__main__":
    unittest.main()
