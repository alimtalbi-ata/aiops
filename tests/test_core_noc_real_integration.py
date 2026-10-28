"""Real HTTP Core + PostgreSQL 16 integration; no mocks and no production services.

Executed only in the isolated GitHub Actions job with ephemeral PostgreSQL.
The internal credential is CI-only. This is NOT a tenant A/B authorization test.
"""
import os
import unittest

import psycopg
import requests
from psycopg.types.json import Jsonb

BASE = "http://127.0.0.1:1810"
TOKEN = os.environ["AIOPS_INTERNAL_TOKEN"]
DATABASE_URL = os.environ["DATABASE_URL"]


class CoreNocRealIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = {
            "DEMO": (True, {}),
            "REPLAY": (True, {}),
            "STORY": (True, {}),
            "LIVE": (True, {}),
            "OBSERVED": (False, {}),
            "TENANT_A": (True, {"metadata": {"ownerTenantId": "PRIVATE-TENANT-A"}}),
            "TENANT_B": (True, {"metadata": {"orgRef": "PRIVATE-TENANT-B"}}),
            "NULL_SCOPE": (True, {"tenant_id": None}),
        }
        with psycopg.connect(DATABASE_URL) as c:
            for suffix, (synthetic, payload) in cls.cases.items():
                mode = suffix if suffix in ("DEMO", "REPLAY", "STORY", "LIVE") else "DEMO"
                c.execute(
                    "insert into aiops.incidents(incident_id,external_id,title,severity,"
                    "state,opened_at,source,synthetic,payload) "
                    "values(%s,%s,%s,'P1','OPEN',now(),'ci',%s,%s)",
                    ("INC-CI-NOC-" + suffix, "CI-NOC-" + suffix,
                     "Ephemeral CI case", synthetic, Jsonb(payload)),
                )
                c.execute(
                    "insert into aiops.runs(run_id,incident_id,mode,scenario_id,"
                    "status,idempotency_key) values(%s,%s,%s,'CI-NOC','CREATED',%s)",
                    ("RUN-CI-NOC-" + suffix, "INC-CI-NOC-" + suffix,
                     mode, "ci-noc-" + suffix),
                )
            c.execute(
                "insert into aiops.runs(run_id,incident_id,mode,scenario_id,"
                "status,idempotency_key) values('RUN-CI-NOC-DANGLING',"
                "'INC-CI-NOC-MISSING','DEMO','CI-NOC','CREATED','ci-noc-dangling')"
            )

    @classmethod
    def tearDownClass(cls):
        with psycopg.connect(DATABASE_URL) as c:
            c.execute("delete from aiops.runs where run_id like 'RUN-CI-NOC-%'")
            c.execute("delete from aiops.incidents where incident_id like 'INC-CI-NOC-%'")

    def read(self, suffix, token=TOKEN):
        headers = {} if token is None else {"Authorization": "Bearer " + token}
        return requests.get(BASE + "/api/noc/runs/RUN-CI-NOC-" + suffix,
                            headers=headers, timeout=3, allow_redirects=False)

    def assert_private_denial(self, response):
        self.assertEqual(response.status_code, 503, response.text)
        self.assertEqual(response.headers.get("cache-control"), "no-store")
        self.assertNotIn("PRIVATE-TENANT", response.text)
        self.assertNotIn("RUN-CI-NOC", response.text)

    def test_actual_postgres_and_core_health(self):
        r = requests.get(BASE + "/health", timeout=3)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["component"], "core")

    def test_synthetic_modes_are_bounded_unattested_reads(self):
        for mode in ("DEMO", "REPLAY", "STORY"):
            with self.subTest(mode=mode):
                r = self.read(mode)
                self.assertEqual(r.status_code, 200, r.text)
                self.assertEqual(r.headers.get("cache-control"), "no-store")
                body = r.json()
                self.assertEqual(body["run"], {
                    "run_id": "RUN-CI-NOC-" + mode,
                    "incident_id": "INC-CI-NOC-" + mode,
                    "mode": mode, "status": "CREATED"})
                self.assertEqual(body["data_classification"], "SYNTHETIC_CANONICAL_RUN")
                self.assertIs(body["runtime_authenticated"], False)
                self.assertIs(body["tenant_acl_qualified"], False)
                self.assertIs(body["live_remediation_authorized"], False)
                self.assertNotIn("payload", r.text)
                self.assertNotIn("idempotency_key", r.text)

    def test_missing_or_invalid_internal_token_is_rejected(self):
        for token in (None, "bad-token", "Bearer " + TOKEN, TOKEN + " extra"):
            with self.subTest(token=token):
                r = self.read("DEMO", token=token)
                self.assertEqual(r.status_code, 401, r.text)
                self.assertEqual(r.headers.get("cache-control"), "no-store")
                self.assertEqual(r.headers.get("www-authenticate"), "Bearer")
                self.assertNotIn("RUN-CI-NOC", r.text)

    def test_live_observed_and_missing_incidents_fail_closed(self):
        for suffix in ("LIVE", "OBSERVED", "DANGLING", "ABSENT", "RUN!BAD"):
            with self.subTest(suffix=suffix):
                self.assert_private_denial(self.read(suffix))

    def test_tenant_a_b_and_null_scope_all_fail_closed(self):
        for suffix in ("TENANT_A", "TENANT_B", "NULL_SCOPE"):
            with self.subTest(suffix=suffix):
                self.assert_private_denial(self.read(suffix))


if __name__ == "__main__":
    unittest.main()
