"""Real disposable PG16/TLS tests for seven-event Core source binding v1.

Inherits the six existing PG16 fixture assertions, then tests an independently
authenticated v2 seven-event manifest. Synthetic-only; no GLPI/IdP network.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import ssl
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import requests
import test_core_actor_canonical_seven_pg16 as fixture

from core import actor_canonical_seven_source as binding


class V2SourceHandler(fixture.SourceHandler):
    """A distinct HTTPS service credential and Core-owned SQL dispatch."""

    def do_POST(self):
        if self.path != "/v2/canonical-seven-readback":
            return super().do_POST()
        from core.canonical_seven_https_adapter import dispatch_canonical_seven
        import psycopg
        try:
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length) if 1 <= length <= 8192 else b""
            status, proof = dispatch_canonical_seven(
                method="POST", path=self.path,
                tls=isinstance(self.connection, ssl.SSLSocket),
                authorization=self.headers.get("Authorization", ""),
                body=body, client_id=fixture.CLIENT,
                client_secret=fixture.SECRET,
                connect=lambda: psycopg.connect(self.server.db_url),
                source=fixture.SOURCE,
                source_issuer="core-source-disposable-authority",
                now=datetime.now(timezone.utc))
            if status != 200:
                return self.reply(status, proof)
            tamper = getattr(self.server, "tamper", None)
            if tamper == "hash":
                proof["events"][3]["full_event_hash"] = "a" * 64
            elif tamper == "payload":
                proof["events"][2]["payload"]["metric"] = "forged"
            elif tamper == "order":
                proof["events"].reverse()
            elif tamper == "missing":
                proof["events"].pop()
            elif tamper == "domain":
                proof["events"][1]["full_event_hash"] = proof["events"][1]["payload_hash"]
            elif tamper == "issuer":
                proof["issuer"] = "attacker"
            elif tamper == "future":
                proof["events"][0]["full_event"]["known_at"] += 3600
            elif tamper == "revoked":
                proof["revoked"] = True
            elif tamper == "stale_attestation":
                proof["observed_at"] -= 3600
            elif tamper == "expired_attestation":
                proof["expires_at"] = int(time.time()) - 10
            self.server.calls += 1
            return self.reply(200, proof)
        except Exception:
            return self.reply(503, {"decision": "UNKNOWN"})


@unittest.skipUnless(os.environ.get("AIOPS_XREF_CI_DISPOSABLE") == "1"
                     and os.environ.get("GITHUB_ACTIONS") == "true",
                     "dedicated disposable PostgreSQL 16 CI only")
class CanonicalSevenBindingPG16(fixture.CanonicalSevenSourcePG16):
    """Existing six source tests + new v2 adversarial full/payload-domain tests."""

    def setUp(self):
        with patch.object(fixture, "SourceHandler", V2SourceHandler):
            super().setUp()
        self.server.tamper = None
        cfg = {"tenant_id": fixture.TENANT, "glpi_instance_id": "GLPI-A",
               "url": f"https://{fixture.IP}:{fixture.PORT}/v2/canonical-seven-readback",
               "issuer": "core-source-disposable-authority",
               "client_id": fixture.CLIENT, "client_secret": fixture.SECRET}
        self.v2env = patch.dict(os.environ, {
            "AIOPS_XREF_ACTOR_CANONICAL_SEVEN_JSON": json.dumps([cfg])})
        self.v2env.start()

    def tearDown(self):
        self.v2env.stop()
        super().tearDown()

    def v2read(self, expected=None, claims=None, record=None):
        event = fixture.event_at(1)
        row = {"tenant_id": fixture.TENANT, "run_id": fixture.RUN, "incident_id": fixture.INCIDENT,
               "glpi_entity_id": fixture.ENTITY,
               "source_event_id": event["source_event_id"],
               "source_payload_hash": fixture.canonical_hash(event)}
        return binding.canonical_seven_preflight(
            self.claims if claims is None else claims,
            self.expected if expected is None else expected,
            row if record is None else record, int(time.time()))

    def test_v2_core_https_adapter_is_not_portable_authority(self):
        """Real TLS listener delegates to Core-owned dispatch, never ALLOW."""
        from core.canonical_seven_https_adapter import dispatch_canonical_seven
        with self.psycopg.connect(self.db_url) as db:
            db.execute((fixture.MIG / "014_hitl_reject_terminal_receipts.sql")
                       .read_text(encoding="utf-8"))
        def audit():
            with self.psycopg.connect(self.db_url) as db:
                return {
                    "nonce_013": db.execute(
                        "select count(*) from aiops.actor_delegation_nonce_ledger"
                    ).fetchone()[0],
                    "revocation_013": db.execute(
                        "select count(*) from aiops.actor_delegation_revocations"
                    ).fetchone()[0],
                    "terminal_014": db.execute(
                        "select count(*) from aiops.hitl_reject_terminal_receipts"
                    ).fetchone()[0],
                }
        before = audit()
        request = {k: self.expected[k] for k in binding._SCOPE
                   if k in self.expected}
        request.update(actor_subject=self.claims["sub"],
                       actor_issuer=self.claims["iss"])
        body = json.dumps(request).encode("utf-8")
        auth = "Basic " + base64.b64encode(
            (fixture.CLIENT + ":" + fixture.SECRET).encode()).decode()
        def dispatch(**changes):
            args = {
                "method": "POST", "path": "/v2/canonical-seven-readback",
                "tls": True, "authorization": auth, "body": body,
                "client_id": fixture.CLIENT, "client_secret": fixture.SECRET,
                "connect": lambda: self.psycopg.connect(self.db_url),
                "source": fixture.SOURCE,
                "source_issuer": "core-source-disposable-authority",
                "now": datetime.now(timezone.utc),
            }
            return dispatch_canonical_seven(**{**args, **changes})
        self.assertEqual(dispatch(tls=False)[0], 503)
        self.assertEqual(dispatch(authorization="Basic invalid")[0], 401)
        self.assertEqual(dispatch(body=b"{}")[0], 404)
        self.assertEqual(dispatch(body=json.dumps(
            {**request, "actor_subject": "idp|foreign"}).encode())[0], 404)
        self.assertEqual(dispatch(connect=lambda: (_ for _ in ()).throw(
            RuntimeError("synthetic SQL outage")))[0], 503)
        status, proof = dispatch()
        self.assertEqual(status, 200)
        self.assertEqual(proof["issuer"], "core-source-disposable-authority")
        self.assertNotEqual(proof["issuer"], proof["actor_issuer"])
        self.assertEqual(len(proof["events"]), 7)
        self.assertEqual([e["sequence"] for e in proof["events"]], list(range(1, 8)))
        self.assertTrue(all(e["payload_hash"] != e["full_event_hash"]
                            for e in proof["events"]))
        with requests.Session() as session:
            session.trust_env = False
            url = f"https://{fixture.IP}:{fixture.PORT}/v2/canonical-seven-readback"
            bad = session.post(url, json=request,
                               auth=(fixture.CLIENT, "wrong-secret"),
                               verify=True, timeout=5)
            self.assertEqual(bad.status_code, 401)
            self.assertEqual(bad.json(), {"decision": "UNKNOWN"})
            good = session.post(url, json=request,
                                auth=(fixture.CLIENT, fixture.SECRET),
                                verify=True, timeout=5)
            self.assertEqual(good.status_code, 200)
            self.assertEqual(good.json()["events"], proof["events"])
        event = fixture.event_at(1)
        record = {
            "tenant_id": fixture.TENANT, "run_id": fixture.RUN,
            "incident_id": fixture.INCIDENT, "glpi_entity_id": fixture.ENTITY,
            "source_event_id": event["source_event_id"],
            "source_payload_hash": fixture.canonical_hash(event),
        }
        receipt = binding.canonical_seven_source_receipt(
            self.claims, self.expected, record, int(time.time()))
        self.assertIsNotNone(receipt)
        self.assertEqual(receipt["decision"], "UNKNOWN")
        self.assertEqual(receipt["link_status"], "UNKNOWN")
        self.assertEqual(receipt["portable_signature"], "NONE")
        self.assertEqual(receipt["event_count"], 7)
        self.assertEqual(receipt["hash_domains"]["acme_full_event_equivalence"],
                         "NOT_VERIFIED")
        self.assertEqual(before, audit())
        output = os.environ.get("AIOPS_CORE_SEVEN_RECEIPT_DIR")
        if output:
            machine = {
                "schema": "aiops.core-https-seven-adapter-receipt.v1",
                "source_head": os.environ["AIOPS_EXPECTED_HEAD_SHA"],
                "source_issuer": proof["issuer"],
                "actor_issuer_distinct": proof["issuer"] != proof["actor_issuer"],
                "transport": "DISPOSABLE_TLS_BASIC_BOUND",
                "portable_signature": "NONE",
                "decision": "UNKNOWN", "link_status": "UNKNOWN",
                "human_glpi_attested": False,
                "source_proof_sha256": binding._digest(
                    binding.RECEIPT_PROOF_DOMAIN, proof),
                "consumer_receipt_sha256": receipt["receipt_sha256"],
                "hash_domains": receipt["hash_domains"],
                "events": receipt["events"],
                "negative_http": {
                    "missing_tls": 503, "invalid_basic": 401,
                    "malformed_scope": 404, "foreign_actor": 404,
                    "sql_failure": 503, "invalid_basic_over_tls": 401,
                },
                "audit_before": before, "audit_after": audit(),
                "execution_allowed": False, "effect_allowed": False,
            }
            machine["receipt_sha256"] = hashlib.sha256(json.dumps(
                machine, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
            directory = Path(output)
            directory.mkdir(parents=True, exist_ok=True)
            (directory / "core-https-adapter.json").write_text(
                json.dumps(machine, sort_keys=True, indent=2) + "\n")

    def test_v2_core_owned_pg_producer_seven_negative_and_redacted_receipt(self):
        """Core-owned SQL producer, not a test-only fixture algorithm.

        Seven adversarial readbacks must fail before any positive receipt.
        No production authorization or external GLPI rights are inferred.
        """
        from core.canonical_seven_pg_source import read_canonical_seven
        now = datetime.now(timezone.utc)
        request = {k: self.expected[k] for k in binding._SCOPE
                   if k in self.expected}
        request.update(actor_subject=self.claims["sub"],
                       actor_issuer=self.claims["iss"])
        def produce(req):
            with self.psycopg.connect(self.db_url) as conn:
                return read_canonical_seven(
                    conn, req, source=fixture.SOURCE,
                    issuer="core-source-disposable-authority",
                    now=datetime.now(timezone.utc))
        proof = produce(request)
        self.assertIsNotNone(proof)
        event = fixture.event_at(1)
        record = {"source_event_id": event["source_event_id"],
                  "source_payload_hash": fixture.canonical_hash(event)}
        self.assertTrue(binding._validate(
            proof, request, record, "core-source-disposable-authority",
            int(time.time()), int(time.time()) + 120))
        self.assertEqual(len(proof["events"]), 7)
        self.assertTrue(all(e["payload_hash"] != e["full_event_hash"]
                            for e in proof["events"]))
        negatives = {}
        for label, delta in (
                ("foreign_actor", {"actor_subject": "idp|foreign"}),
                ("foreign_tenant", {"tenant_id": "TEN-B"}),
                ("foreign_run", {"run_id": "RUN-B"}),
                ("foreign_ticket", {"ticket_id": "999"}),
                ("foreign_entity", {"glpi_entity_id": "8"})):
            negatives[label] = "UNKNOWN" if produce({**request, **delta}) is None else "ERROR"
        with self.psycopg.connect(self.db_url) as conn:
            conn.execute("update public.ci_actor_source_grants set revoked=true")
        negatives["revoked_grant"] = "UNKNOWN" if produce(request) is None else "ERROR"
        with self.psycopg.connect(self.db_url) as conn:
            conn.execute("update public.ci_actor_source_grants set revoked=false,"
                         "expires_at=clock_timestamp()-interval '1 second'")
        negatives["expired_grant"] = "UNKNOWN" if produce(request) is None else "ERROR"
        with self.psycopg.connect(self.db_url) as conn:
            conn.execute("update public.ci_actor_source_grants "
                         "set expires_at=clock_timestamp()+interval '3 minutes'")
        self.assertEqual(negatives, {key: "UNKNOWN" for key in negatives})
        self.assertIsNotNone(produce(request))
        with self.psycopg.connect(self.db_url) as conn:
            conn.execute((fixture.MIG / "014_hitl_reject_terminal_receipts.sql")
                         .read_text(encoding="utf-8"))
            audit = {
                "nonce_013": conn.execute(
                    "select count(*) from aiops.actor_delegation_nonce_ledger"
                ).fetchone()[0],
                "revocation_013": conn.execute(
                    "select count(*) from aiops.actor_delegation_revocations"
                ).fetchone()[0],
                "terminal_014": conn.execute(
                    "select count(*) from aiops.hitl_reject_terminal_receipts"
                ).fetchone()[0],
            }
        self.assertEqual(audit, {"nonce_013": 1, "revocation_013": 1,
                                 "terminal_014": 0})
        output = os.environ.get("AIOPS_CORE_SEVEN_RECEIPT_DIR")
        if output:
            machine = {
                "schema": "aiops.core-owned-seven-pg-producer-receipt.v1",
                "source_head": os.environ["AIOPS_EXPECTED_HEAD_SHA"],
                "producer": "core.canonical_seven_pg_source.read_canonical_seven",
                "synthetic_only": True,
                "transport": "DISPOSABLE_TLS_BASIC_BOUND",
                "portable_signature": "NONE",
                "decision": "UNKNOWN",
                "link_status": "UNKNOWN",
                "human_glpi_attested": False,
                "acme_full_event_equivalence": "NOT_VERIFIED",
                "hash_domains": {"payload": binding.PAYLOAD_DOMAIN,
                                 "full_event": binding.FULL_DOMAIN},
                "source_proof_sha256": binding._digest(
                    binding.RECEIPT_PROOF_DOMAIN, proof),
                "events": [{
                    "sequence": e["sequence"],
                    "source_event_id": e["source_event_id"],
                    "payload_sha256": e["payload_hash"],
                    "full_event_sha256": e["full_event_hash"],
                } for e in proof["events"]],
                "negative_cases": negatives,
                "audit_013_014": audit,
                "execution_allowed": False,
            }
            machine["receipt_sha256"] = hashlib.sha256(json.dumps(
                machine, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
            directory = Path(output)
            directory.mkdir(parents=True, exist_ok=True)
            (directory / "core-owned-producer.json").write_text(
                json.dumps(machine, sort_keys=True, indent=2) + "\n")

    def test_v2_seven_full_and_payload_hash_domains_and_unknown(self):
        self.assertTrue(self.v2read())
        self.assertEqual(json.loads(fixture.actor_resource_authz._reply().body)["decision"],
                         "UNKNOWN")
        self.assertNotEqual(binding.PAYLOAD_DOMAIN, binding.FULL_DOMAIN)

    def test_v2_tampered_manifest_never_passes(self):
        for attack in ("hash", "payload", "order", "missing", "domain",
                       "issuer", "future", "revoked"):
            with self.subTest(attack=attack):
                self.server.tamper = attack
                self.assertFalse(self.v2read())
        self.server.tamper = None
        self.assertTrue(self.v2read())

    def test_v2_actor_tenant_run_ticket_entity_and_source_mismatch(self):
        for delta in ({"tenant_id": "TEN-B"}, {"run_id": "RUN-B"},
                      {"incident_id": "INC-B"}, {"ticket_id": "124"},
                      {"glpi_entity_id": "8"}, {"permission": "ticket:write"}):
            with self.subTest(delta=delta):
                self.assertFalse(self.v2read(expected={**self.expected, **delta}))
        self.assertFalse(self.v2read(claims={**self.claims, "sub": "idp|bob"}))
        self.assertFalse(self.v2read(claims={**self.claims, "iss": "https://evil.invalid"}))
        self.assertFalse(self.v2read(record={
            "tenant_id": fixture.TENANT, "run_id": fixture.RUN, "incident_id": fixture.INCIDENT,
            "glpi_entity_id": fixture.ENTITY,
            "source_event_id": "EVT-SOURCE-01", "source_payload_hash": "a"*64}))

    def test_v2_revocation_expiry_tls_and_immutable_013(self):
        with self.psycopg.connect(self.db_url) as conn:
            before = (
                conn.execute("select count(*) from aiops.actor_delegation_nonce_ledger").fetchone()[0],
                conn.execute("select count(*) from aiops.actor_delegation_revocations").fetchone()[0])
            conn.execute("update public.ci_actor_source_grants set revoked=true")
        self.assertFalse(self.v2read())
        with self.psycopg.connect(self.db_url) as conn:
            conn.execute("update public.ci_actor_source_grants set revoked=false,"
                         "expires_at=clock_timestamp()-interval '1 second'")
        self.assertFalse(self.v2read())
        with self.psycopg.connect(self.db_url) as conn:
            conn.execute("update public.ci_actor_source_grants set expires_at="
                         "clock_timestamp()+interval '3 minutes'")
        with patch("requests.adapters.DEFAULT_CA_BUNDLE_PATH", requests.certs.where()), \
             patch.object(requests.adapters, "_preloaded_ssl_context",
                          ssl.create_default_context(cafile=requests.certs.where()),
                          create=True):
            self.assertFalse(self.v2read())
        with self.psycopg.connect(self.db_url) as conn:
            after = (
                conn.execute("select count(*) from aiops.actor_delegation_nonce_ledger").fetchone()[0],
                conn.execute("select count(*) from aiops.actor_delegation_revocations").fetchone()[0])
        self.assertEqual(before, (1, 1))
        self.assertEqual(after, before)


    def test_v2_expired_and_stale_attestation_never_writes_013_014(self):
        """Reject stale/expired independently authenticated source responses.

        A valid disposable TLS connection is not a durable authorization.
        The refusal must not consume a nonce or alter terminal audit rows.
        """
        event = fixture.event_at(1)
        record = {
            "tenant_id": fixture.TENANT, "run_id": fixture.RUN,
            "incident_id": fixture.INCIDENT, "glpi_entity_id": fixture.ENTITY,
            "source_event_id": event["source_event_id"],
            "source_payload_hash": fixture.canonical_hash(event),
        }
        with self.psycopg.connect(self.db_url) as conn:
            conn.execute((fixture.MIG / "014_hitl_reject_terminal_receipts.sql")
                         .read_text(encoding="utf-8"))
            def counts():
                return {
                    "nonce_013": conn.execute(
                        "select count(*) from aiops.actor_delegation_nonce_ledger"
                    ).fetchone()[0],
                    "revocation_013": conn.execute(
                        "select count(*) from aiops.actor_delegation_revocations"
                    ).fetchone()[0],
                    "terminal_014": conn.execute(
                        "select count(*) from aiops.hitl_reject_terminal_receipts"
                    ).fetchone()[0],
                }
            before = counts()
        self.assertEqual(before, {"nonce_013": 1, "revocation_013": 1,
                                  "terminal_014": 0})
        try:
            for attack in ("stale_attestation", "expired_attestation"):
                with self.subTest(attack=attack):
                    self.server.tamper = attack
                    self.assertFalse(self.v2read())
                    self.assertIsNone(binding.canonical_seven_source_receipt(
                        self.claims, self.expected, record, int(time.time())))
        finally:
            self.server.tamper = None
        with self.psycopg.connect(self.db_url) as conn:
            after = {
                "nonce_013": conn.execute(
                    "select count(*) from aiops.actor_delegation_nonce_ledger"
                ).fetchone()[0],
                "revocation_013": conn.execute(
                    "select count(*) from aiops.actor_delegation_revocations"
                ).fetchone()[0],
                "terminal_014": conn.execute(
                    "select count(*) from aiops.hitl_reject_terminal_receipts"
                ).fetchone()[0],
            }
        self.assertEqual(after, before)
        self.assertTrue(self.v2read())
        self.assertEqual(json.loads(fixture.actor_resource_authz._reply().body)
                         ["decision"], "UNKNOWN")
        out = os.environ.get("AIOPS_CORE_SEVEN_RECEIPT_DIR")
        if out:
            machine = {
                "schema": "aiops.core-seven-freshness-negative.v1",
                "source_head": os.environ["AIOPS_EXPECTED_HEAD_SHA"],
                "synthetic_only": True,
                "transport": "TLS_AUTHENTICATED_NONPORTABLE",
                "portable_signature": "NONE",
                "decision": "UNKNOWN",
                "link_status": "UNKNOWN",
                "human_glpi_attested": False,
                "acme_full_event_equivalence": "NOT_VERIFIED",
                "negative_cases": {
                    "stale_attestation": "UNKNOWN",
                    "expired_attestation": "UNKNOWN",
                },
                "audit_before": before,
                "audit_after": after,
                "valid_source_recovery": True,
                "execution_allowed": False,
                "effect_allowed": False,
            }
            machine["receipt_sha256"] = hashlib.sha256(json.dumps(
                machine, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
            path = Path(out)
            path.mkdir(parents=True, exist_ok=True)
            (path / "freshness-expiry-negative.json").write_text(
                json.dumps(machine, sort_keys=True, indent=2) + "\n")

    def test_v2_receipt_is_machine_readable_and_never_authorizes(self):
        event = fixture.event_at(1)
        record = {
            "tenant_id": fixture.TENANT, "run_id": fixture.RUN,
            "incident_id": fixture.INCIDENT, "glpi_entity_id": fixture.ENTITY,
            "source_event_id": event["source_event_id"],
            "source_payload_hash": fixture.canonical_hash(event),
        }
        receipt = binding.canonical_seven_source_receipt(
            self.claims, self.expected, record, int(time.time()))
        self.assertIsInstance(receipt, dict)
        self.assertEqual(receipt["schema"], binding.RECEIPT_SCHEMA)
        self.assertEqual(receipt["decision"], "UNKNOWN")
        self.assertEqual(receipt["link_status"], "UNKNOWN")
        self.assertEqual(receipt["source_preflight"], "PASS_SYNTHETIC_ONLY")
        self.assertEqual(receipt["portable_signature"], "NONE")
        self.assertEqual(receipt["event_count"], 7)
        self.assertEqual([e["sequence"] for e in receipt["events"]], list(range(1, 8)))
        self.assertEqual(receipt["hash_domains"]["payload"], binding.PAYLOAD_DOMAIN)
        self.assertEqual(receipt["hash_domains"]["full_event"], binding.FULL_DOMAIN)
        self.assertEqual(receipt["hash_domains"]["acme_full_event_equivalence"],
                         "NOT_VERIFIED")
        self.assertEqual(receipt["source_event_id"], event["source_event_id"])
        self.assertEqual(receipt["source_payload_hash"], fixture.canonical_hash(event))
        self.assertEqual(receipt["actor_subject_sha256"],
                         hashlib.sha256(self.claims["sub"].encode()).hexdigest())
        self.assertNotIn(self.claims["sub"], json.dumps(receipt))
        digest = receipt["receipt_sha256"]
        self.assertEqual(digest, binding._digest(
            binding.RECEIPT_HASH_DOMAIN,
            {k: v for k, v in receipt.items() if k != "receipt_sha256"}))
        self.assertEqual(len({e["payload_sha256"] for e in receipt["events"]}), 7)
        self.assertEqual(len({e["full_event_sha256"] for e in receipt["events"]}), 7)
        self.assertTrue(all(e["payload_sha256"] != e["full_event_sha256"]
                            for e in receipt["events"]))
        self.assertNotIn("ALLOW", json.dumps(receipt))
        self.assertNotIn("VERIFIED", receipt["source_preflight"])

    def test_v2_receipt_fail_closed_and_013_replay_audit_unchanged(self):
        event = fixture.event_at(1)
        record = {
            "tenant_id": fixture.TENANT, "run_id": fixture.RUN,
            "incident_id": fixture.INCIDENT, "glpi_entity_id": fixture.ENTITY,
            "source_event_id": event["source_event_id"],
            "source_payload_hash": fixture.canonical_hash(event),
        }
        def receipt(claims=None, expected=None):
            return binding.canonical_seven_source_receipt(
                self.claims if claims is None else claims,
                self.expected if expected is None else expected,
                record, int(time.time()))
        self.assertIsNotNone(receipt())
        for attack in ("hash", "payload", "order", "missing", "domain",
                       "issuer", "future", "revoked"):
            with self.subTest(attack=attack):
                self.server.tamper = attack
                self.assertIsNone(receipt())
        self.server.tamper = None
        self.assertIsNone(receipt(claims={**self.claims, "sub": "idp|foreign"}))
        self.assertIsNone(receipt(expected={**self.expected, "tenant_id": "TEN-B"}))
        self.assertIsNone(receipt(expected={**self.expected, "ticket_id": "999"}))
        self.assertIsNone(receipt(expected={**self.expected, "glpi_entity_id": "8"}))
        self.assertIsNone(receipt(expected={**self.expected, "run_id": "RUN-B"}))
        digest = lambda s: hashlib.sha256(s.encode()).hexdigest()
        with self.psycopg.connect(self.db_url) as conn:
            before = (
                conn.execute("select count(*) from aiops.actor_delegation_nonce_ledger").fetchone()[0],
                conn.execute("select count(*) from aiops.actor_delegation_revocations").fetchone()[0])
            replay = conn.execute(
                "select aiops.actor_delegation_consume(%s,%s,%s,%s,%s,%s,%s)",
                (fixture.TENANT, fixture.ISSUER, digest(fixture.SUBJECT),
                 digest("ci-source-jti"), digest("ci-source-nonce"),
                 digest("ci-source-resource"),
                 datetime.now(timezone.utc) + timedelta(minutes=2))).fetchone()[0]
            revoked = conn.execute(
                "select aiops.actor_delegation_consume(%s,%s,%s,%s,%s,%s,%s)",
                (fixture.TENANT, fixture.ISSUER, digest(fixture.SUBJECT),
                 digest("ci-source-revoked-jti"), digest("fresh-nonce"),
                 digest("ci-source-resource"),
                 datetime.now(timezone.utc) + timedelta(minutes=2))).fetchone()[0]
            after = (
                conn.execute("select count(*) from aiops.actor_delegation_nonce_ledger").fetchone()[0],
                conn.execute("select count(*) from aiops.actor_delegation_revocations").fetchone()[0])
        self.assertFalse(replay)
        self.assertFalse(revoked)
        self.assertEqual(before, (1, 1))
        self.assertEqual(after, before)
        # Source evidence is not an actor permission or a nonce authorization.
        self.assertIsNotNone(receipt())
        self.assertEqual(json.loads(fixture.actor_resource_authz._reply().body)["decision"],
                         "UNKNOWN")


    def test_z_v2_native_014_audit_restore_and_fail_closed_receipt(self):
        """One disposable PG16 authority, seven sources and 013/014 audit.

        The 014 row below is an explicitly synthetic audit fixture, not a
        claim that Core's terminal handler or a real human GLPI right ran.
        The archive is destroyed locally; only a redacted receipt survives.
        """
        import subprocess
        import tempfile
        import uuid
        from urllib.parse import urlsplit, urlunsplit

        source_event = fixture.event_at(1)
        record = {
            "tenant_id": fixture.TENANT, "incident_id": fixture.INCIDENT,
            "run_id": fixture.RUN, "glpi_entity_id": fixture.ENTITY,
            "source_event_id": source_event["source_event_id"],
            "source_payload_hash": fixture.canonical_hash(source_event),
        }
        def read(claims=None, expected=None):
            return binding.canonical_seven_source_receipt(
                self.claims if claims is None else claims,
                self.expected if expected is None else expected,
                record, int(time.time()))

        source_receipt = read()
        self.assertIsNotNone(source_receipt)
        self.assertEqual(source_receipt["decision"], "UNKNOWN")
        self.assertEqual(source_receipt["event_count"], 7)
        self.assertEqual(source_receipt["hash_domains"]["acme_full_event_equivalence"],
                         "NOT_VERIFIED")
        self.assertTrue(all(e["payload_sha256"] != e["full_event_sha256"]
                            for e in source_receipt["events"]))
        for changed in ({"tenant_id": "TEN-FOREIGN"},
                        {"run_id": "RUN-FOREIGN"},
                        {"ticket_id": "TICKET-FOREIGN"},
                        {"glpi_entity_id": "ENTITY-FOREIGN"}):
            self.assertIsNone(read(expected={**self.expected, **changed}))
        self.assertIsNone(read(claims={**self.claims, "sub": "foreign-subject"}))
        self.server.tamper = "hash"
        self.assertIsNone(read())
        self.server.tamper = "revoked"
        self.assertIsNone(read())
        self.server.tamper = None

        suffix = uuid.uuid4().hex
        ids = {k: "CI-SEVEN-" + k.upper() + "-" + suffix
               for k in ("analysis", "critique", "proposal", "approval", "event")}
        digest = hashlib.sha256(("CI-SEVEN-014-" + suffix).encode()).hexdigest()
        lease_hash = hashlib.sha256(("DISPOSABLE-LEASE-" + suffix).encode()).hexdigest()
        evidence_ids = json.dumps(["EVIDENCE-SOURCE-01"])
        audit_payload = {
            "schema": "aiops.core-hitl-reject-terminal-receipt.v1",
            "status": "DEAD", "synthetic_fixture": True,
            "tenant_id": fixture.TENANT, "run_id": fixture.RUN,
            "proposal_hash": digest, "attempts": 8,
            "execution_allowed": False, "effect_allowed": False,
        }
        audit_hash = hashlib.sha256(json.dumps(
            audit_payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        with self.psycopg.connect(self.db_url) as db:
            db.execute((fixture.MIG / "014_hitl_reject_terminal_receipts.sql")
                       .read_text(encoding="utf-8"))
            db.execute(
                "insert into aiops.analysis_records "
                "(analysis_id,run_id,idempotency_key,revision,contract_version,"
                "provider,model,prompt_version,evidence_ids,evidence_set_hash,"
                "output,confidence,status) "
                "values(%s,%s,%s,1,'ci','ci-fixture','none','ci',%s,%s,"
                "%s::jsonb,0.5,'VALID')",
                (ids["analysis"], fixture.RUN, "analysis-" + suffix,
                 evidence_ids, digest, json.dumps({"recommended_actions": [{"action_id": "CI-SOURCE",
                     "risk_tier": "LOW", "target_ci_id": "CI-SYNTHETIC",
                     "advisory_only": True, "requires_human_approval": True}]})))
            db.execute(
                "insert into aiops.critique_records "
                "(critique_id,idempotency_key,analysis_id,run_id,contract_version,"
                "provider,model,validated,evidence_ids,output,diagnostic_confidence) "
                "values(%s,%s,%s,%s,'ci','ci-fixture','none',true,%s,%s::jsonb,0.5)",
                (ids["critique"], "critique-" + suffix, ids["analysis"],
                 fixture.RUN, evidence_ids, json.dumps({"issues": []})))
            db.execute(
                "insert into aiops.action_proposals "
                "(proposal_id,run_id,analysis_id,critique_id,source_action_id,"
                "proposal_revision,target_ci_id,action_type,risk_tier,evidence_ids,"
                "preconditions,expected_postconditions,proposal_hash,status,expires_at) "
                "values(%s,%s,%s,%s,'CI-SOURCE',1,'CI-SYNTHETIC',"
                "'COLLECT_DIAGNOSTICS','LOW',%s,'[\"ci precondition\"]',"
                "'[\"ci postcondition\"]',%s,'PROPOSED',"
                "now()+interval '1 hour')",
                (ids["proposal"], fixture.RUN, ids["analysis"],
                 ids["critique"], evidence_ids, digest))
            db.execute(
                "insert into aiops.approval_records "
                "(approval_id,proposal_id,proposal_hash,actor_id,actor_role,"
                "decision,nonce,expires_at,audit) "
                "values(%s,%s,%s,'UNATTESTED_CI','test_only','REJECT',"
                "%s,now()+interval '1 hour',%s::jsonb)",
                (ids["approval"], ids["proposal"], digest, "nonce-" + suffix,
                 json.dumps({"synthetic": True, "identity_attested": False})))
            db.execute("update aiops.action_proposals set status='REJECTED' "
                       "where proposal_id=%s", (ids["proposal"],))
            db.execute(
                "insert into aiops.hitl_decision_outbox "
                "(event_id,proposal_id,run_id,proposal_hash,proposal_revision,"
                "decision,source_status,approval_id,status,attempts,lease_owner,"
                "lease_token,lease_until) "
                "values(%s,%s,%s,%s,1,'REJECT','REJECTED',%s,'DEAD',8,"
                "'ci-disposable','redacted-in-artifact',"
                "now()-interval '2 seconds')",
                (ids["event"], ids["proposal"], fixture.RUN, digest,
                 ids["approval"]))
            db.execute(
                "insert into aiops.hitl_reject_terminal_receipts "
                "(event_id,tenant_id,run_id,proposal_id,proposal_hash,"
                "proposal_revision,actor_id,lease_owner,lease_token_sha256,"
                "attempts,lease_expired_at,dead_at,receipt_payload,receipt_sha256) "
                "values(%s,%s,%s,%s,%s,1,'ci-unattested','ci-disposable',"
                "%s,8,now()-interval '2 seconds',now(),%s::jsonb,%s)",
                (ids["event"], fixture.TENANT, fixture.RUN, ids["proposal"],
                 digest, lease_hash, json.dumps(audit_payload), audit_hash))
        def snapshot(url):
            with self.psycopg.connect(url) as db:
                return {
                    "evidence": db.execute(
                        "select count(*) from aiops.evidence where source=%s",
                        (fixture.SOURCE,)).fetchone()[0],
                    "run_events": db.execute(
                        "select count(*) from aiops.run_events where run_id=%s",
                        (fixture.RUN,)).fetchone()[0],
                    "nonce_013": db.execute(
                        "select count(*) from aiops.actor_delegation_nonce_ledger").fetchone()[0],
                    "revocation_013": db.execute(
                        "select count(*) from aiops.actor_delegation_revocations").fetchone()[0],
                    "audit_014": db.execute(
                        "select receipt_sha256 from aiops.hitl_reject_terminal_receipts "
                        "where event_id=%s", (ids["event"],)).fetchone(),
                }
        before = snapshot(self.db_url)
        self.assertEqual(before, {
            "evidence": 7, "run_events": 7, "nonce_013": 1,
            "revocation_013": 1, "audit_014": (audit_hash,)})
        # An aborted append must not survive; no destructive DOWN/DROP of audit.
        rollback_jti = hashlib.sha256(("rollback-" + suffix).encode()).hexdigest()
        with self.assertRaisesRegex(RuntimeError, "disposable rollback"):
            with self.psycopg.connect(self.db_url) as db:
                db.execute(
                    "insert into aiops.actor_delegation_revocations "
                    "(issuer,jti_sha256,source_event_id) values(%s,%s,%s)",
                    (fixture.ISSUER, rollback_jti, "ROLLBACK-TEST"))
                raise RuntimeError("disposable rollback")
        self.assertEqual(snapshot(self.db_url), before)

        client = Path("/usr/lib/postgresql/16/bin")
        for name in ("pg_dump", "pg_restore"):
            self.assertTrue((client / name).is_file(), "PG16 native client required")
            self.assertIn("(PostgreSQL) 16.", subprocess.run(
                [str(client / name), "--version"], check=True, text=True,
                capture_output=True, timeout=10).stdout)
        parsed = urlsplit(self.db_url)
        restore_name = "aiops_core_seven_014_restore_ci"
        restore_url = urlunsplit((parsed.scheme, parsed.netloc,
                                 "/" + restore_name, "", ""))
        created = False
        try:
            with self.psycopg.connect(self.admin_url, autocommit=True) as db:
                db.execute(self.sql.SQL("create database {}").format(
                    self.sql.Identifier(restore_name)))
                created = True
            with tempfile.TemporaryDirectory(prefix="ci-seven-014-") as tmp:
                archive = Path(tmp) / "synthetic.pgcustom"
                subprocess.run(
                    [str(client / "pg_dump"), "--format=custom", "--no-owner",
                     "--no-acl", "--file=" + str(archive),
                     "--dbname=" + self.db_url],
                    check=True, timeout=90, capture_output=True)
                archive_sha = hashlib.sha256(archive.read_bytes()).hexdigest()
                self.assertGreater(archive.stat().st_size, 1000)
                corrupt = Path(tmp) / "corrupt.pgcustom"
                corrupt.write_bytes(archive.read_bytes() + b"CORRUPTED")
                self.assertNotEqual(hashlib.sha256(corrupt.read_bytes()).hexdigest(),
                                    archive_sha)
                self.assertEqual(hashlib.sha256(archive.read_bytes()).hexdigest(),
                                 archive_sha)
                subprocess.run(
                    [str(client / "pg_restore"), "--no-owner", "--no-acl",
                     "--single-transaction", "--exit-on-error",
                     "--dbname=" + restore_url, str(archive)],
                    check=True, timeout=120, capture_output=True)
                self.assertEqual(snapshot(restore_url), before)
                with self.psycopg.connect(restore_url) as db:
                    for migration in ("013_actor_delegation_replay_ledger.sql",
                                      "014_hitl_reject_terminal_receipts.sql"):
                        db.execute((fixture.MIG / migration).read_text(encoding="utf-8"))
                self.assertEqual(snapshot(restore_url), before)
                for statement in (
                    "update aiops.hitl_reject_terminal_receipts "
                    "set attempts=9 where event_id=%s",
                    "delete from aiops.hitl_reject_terminal_receipts where event_id=%s",
                ):
                    with self.assertRaises(self.psycopg.Error):
                        with self.psycopg.connect(restore_url) as db:
                            db.execute(statement, (ids["event"],))
                self.assertEqual(snapshot(restore_url), before)
                out = os.environ.get("AIOPS_CORE_SEVEN_RECEIPT_DIR")
                if out:
                    path = Path(out)
                    path.mkdir(parents=True, exist_ok=True)
                    machine = {
                        "schema": "aiops.core-seven-014-disposable-recovery.v1",
                        "source_head": os.environ["AIOPS_EXPECTED_HEAD_SHA"],
                        "source_receipt_schema": binding.RECEIPT_SCHEMA,
                        "source_receipt_sha256": source_receipt["receipt_sha256"],
                        "source_preflight": "PASS_SYNTHETIC_ONLY",
                        "decision": "UNKNOWN", "link_status": "UNKNOWN",
                        "human_glpi_attested": False,
                        "acme_full_event_equivalence": "NOT_VERIFIED",
                        "hash_domains": source_receipt["hash_domains"],
                        "source_event_hashes": source_receipt["events"],
                        "pg_major": 16, "installed": [
                            "001", "004", "009", "010", "011", "012", "013", "014"],
                        "rows": {k: v if isinstance(v, int) else 1
                                 for k, v in before.items()},
                        "archive_sha256": archive_sha, "archive_retained": False,
                        "native_restore": True, "rollback_preserved": True,
                        "audit_013_014_immutable": True, "synthetic_only": True,
                        "execution_allowed": False, "effect_allowed": False,
                    }
                    machine["receipt_sha256"] = hashlib.sha256(json.dumps(
                        machine, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
                    (path / "seven-014-recovery.json").write_text(
                        json.dumps(machine, sort_keys=True, indent=2) + "\n")
        finally:
            if created:
                with self.psycopg.connect(self.admin_url, autocommit=True) as db:
                    db.execute(self.sql.SQL("drop database {} with (force)").format(
                        self.sql.Identifier(restore_name)))
        self.assertEqual(snapshot(self.db_url), before)
        self.assertIsNotNone(read())
        self.assertEqual(json.loads(fixture.actor_resource_authz._reply().body)
                         ["decision"], "UNKNOWN")



    def test_v2_core_written_015_actor_source_readback_and_native_dr(self):
        """Real Core ASGI seven SYN-EVT writes -> independently Basic/TLS readback.

        The actor grant is disposable synthetic provenance, NOT human IdP or
        GLPI authorization. The service issuer and IdP issuer are distinct.
        """
        import subprocess
        import tempfile
        from fastapi.testclient import TestClient
        from core import canonical_seven_pg_source as pgsource
        from core.canonical_seven_https_adapter import dispatch_core_written_seven
        from unittest.mock import patch

        incident, run, tenant = "INC-WRITER-015", "RUN-WRITER-015", "TEN-WRITER"
        actor, actor_issuer = "idp|writer", fixture.ISSUER
        source_issuer = "core-source-disposable-authority"
        request = {
            "tenant_id": tenant, "incident_id": incident, "run_id": run,
            "glpi_instance_id": "GLPI-W", "ticket_id": "789",
            "glpi_entity_id": "9", "permission": "run:read",
            "actor_subject": actor, "actor_issuer": actor_issuer,
        }
        script = (fixture.MIG / "015_core_run_event_idempotency.sql").read_text()
        with self.psycopg.connect(self.db_url) as conn:
            conn.execute(script)
            conn.rollback()
        with self.psycopg.connect(self.db_url) as conn:
            self.assertIsNone(conn.execute(
                "select 1 from information_schema.columns where "
                "table_schema='aiops' and table_name='run_events' "
                "and column_name='event_key'").fetchone())
            conn.execute(script)
            conn.execute(script)
        with self.psycopg.connect(self.db_url) as conn:
            conn.execute(
                "insert into aiops.incidents(incident_id,title,severity,state,"
                "opened_at,source,synthetic,payload) "
                "values(%s,'Core-written synthetic','P4','OPEN',now(),%s,true,%s)",
                (incident, fixture.SOURCE, json.dumps({"tenant_id": tenant})))
            conn.execute(
                "insert into aiops.runs(run_id,incident_id,mode,scenario_id,"
                "status,idempotency_key) values(%s,%s,'DEMO','ACME-CI',"
                "'CREATED','core-written-015')", (run, incident))
            for kind, rid in (
                ("incident", incident), ("run", run),
                ("glpi_instance", "GLPI-W"),
                ("glpi_ticket", "GLPI-W:789"), ("glpi_entity", "GLPI-W:9")
            ):
                conn.execute(
                    "insert into aiops.tenant_resource_ownership "
                    "(resource_kind,resource_id,tenant_id,source_event_id,"
                    "verified,observed_at,known_at) "
                    "values(%s,%s,%s,'SYN-EVT-OWN',true,"
                    "clock_timestamp()-interval '20 seconds',"
                    "clock_timestamp()-interval '10 seconds')",
                    (kind, rid, tenant))
            conn.execute(
                "insert into public.ci_actor_source_grants "
                "(issuer,actor_subject,tenant_id,run_id,incident_id,"
                "glpi_instance_id,ticket_id,glpi_entity_id,permission,"
                "expires_at,revoked) "
                "values(%s,%s,%s,%s,%s,'GLPI-W','789','9','run:read',"
                "clock_timestamp()+interval '3 minutes',false)",
                (actor_issuer, actor, tenant, run, incident))
            for pos in range(1, 8):
                key = f"SYN-EVT-{pos:02d}"
                payload = {
                    "tenant_id": tenant, "incident_id": incident, "run_id": run,
                    "ticket_id": "789", "glpi_entity_id": "9",
                    "source_event_id": key, "sequence": pos,
                    "actor_subject": actor, "actor_issuer": actor_issuer,
                    "source_issuer": source_issuer, "synthetic": True,
                    "metric": f"synthetic-{pos}",
                }
                provenance = {
                    "tenant_id": tenant, "incident_id": incident, "run_id": run,
                    "actor_subject": actor, "actor_issuer": actor_issuer,
                    "source_issuer": source_issuer,
                }
                conn.execute(
                    "insert into aiops.evidence "
                    "(evidence_id,source,external_id,observed_at,known_at,"
                    "claim,confidence,provenance,payload_hash,payload) "
                    "values(%s,%s,%s,clock_timestamp()-interval '20 seconds',"
                    "clock_timestamp()-interval '10 seconds','TEST_ONLY',1,"
                    "%s::jsonb,%s,%s::jsonb)",
                    (f"EVI-WRITER-{pos:02d}", fixture.SOURCE, key,
                     json.dumps(provenance),
                     binding._digest(binding.PAYLOAD_DOMAIN, payload),
                     json.dumps(payload)))
        # This is the actual Core API writer, not a direct SQL run_events seed.
        with patch.dict(os.environ, {"AIOPS_INTERNAL_TOKEN": "ci-core-writer-only"}):
            from core import main
            with patch.object(main, "ADMIN", "ci-core-writer-only"), \
                    patch.object(main, "db",
                                 side_effect=lambda: self.psycopg.connect(self.db_url)):
                with TestClient(main.app) as client:
                    for pos in range(1, 8):
                        key = f"SYN-EVT-{pos:02d}"
                        with self.psycopg.connect(self.db_url) as conn:
                            payload = conn.execute(
                                "select payload from aiops.evidence "
                                "where external_id=%s and source=%s",
                                (key, fixture.SOURCE)).fetchone()[0]
                        response = client.post(
                            f"/api/runs/{run}/events",
                            json={
                                "expected_version": pos, "stage": "INGEST",
                                "event_type": "SYNTHETIC_SOURCE_EVENT",
                                "status": "PASS", "event_key": key,
                                "evidence_ids": [f"EVI-WRITER-{pos:02d}"],
                                "payload": payload,
                            },
                            headers={"Authorization": "Bearer ci-core-writer-only"})
                        self.assertEqual(response.status_code, 200, response.text)
                        self.assertEqual(response.json()["sequence"], pos)
                        self.assertIs(response.json()["idempotent"], False)
                    replay = client.post(
                        f"/api/runs/{run}/events",
                        json={
                            "expected_version": 1, "stage": "INGEST",
                            "event_type": "SYNTHETIC_SOURCE_EVENT",
                            "status": "PASS", "event_key": "SYN-EVT-01",
                            "evidence_ids": ["EVI-WRITER-01"],
                            "payload": self.psycopg.connect(self.db_url).execute(
                                "select payload from aiops.evidence "
                                "where evidence_id='EVI-WRITER-01'").fetchone()[0],
                        },
                        headers={"Authorization": "Bearer ci-core-writer-only"})
                    self.assertEqual(replay.status_code, 200, replay.text)
                    self.assertIs(replay.json()["idempotent"], True)

        def read(req, *, db_url=None, at=None):
            with self.psycopg.connect(db_url or self.db_url) as conn:
                return pgsource.read_core_written_seven(
                    conn, req, source=fixture.SOURCE, issuer=source_issuer,
                    now=at or datetime.now(timezone.utc))

        proof = read(request)
        self.assertIsNotNone(proof)
        self.assertNotEqual(proof["issuer"], proof["actor_issuer"])
        self.assertEqual([e["source_event_id"] for e in proof["events"]],
                         [f"SYN-EVT-{i:02d}" for i in range(1, 8)])
        self.assertTrue(all(e["payload_hash"] != e["full_event_hash"]
                            for e in proof["events"]))
        self.assertTrue(all(e["full_event"]["stage"] == "INGEST"
                            for e in proof["events"]))
        auth = "Basic " + base64.b64encode(
            (fixture.CLIENT + ":" + fixture.SECRET).encode()).decode()
        args = {
            "method": "POST", "path": "/v3/core-written-seven-readback",
            "tls": True, "authorization": auth,
            "body": json.dumps(request).encode(),
            "client_id": fixture.CLIENT, "client_secret": fixture.SECRET,
            "connect": lambda: self.psycopg.connect(self.db_url),
            "source": fixture.SOURCE, "source_issuer": source_issuer,
            "now": datetime.now(timezone.utc),
        }
        status, transport_proof = dispatch_core_written_seven(**args)
        self.assertEqual(status, 200)
        self.assertEqual(transport_proof["events"], proof["events"])
        self.assertEqual(dispatch_core_written_seven(
            **{**args, "tls": False})[0], 503)
        self.assertEqual(dispatch_core_written_seven(
            **{**args, "authorization": "Basic invalid"})[0], 401)

        negatives = {}
        for name, change in (
            ("foreign_actor", {"actor_subject": "idp|foreign"}),
            ("foreign_tenant", {"tenant_id": "TEN-FOREIGN"}),
            ("foreign_run", {"run_id": "RUN-FOREIGN"}),
            ("foreign_incident", {"incident_id": "INC-FOREIGN"}),
            ("foreign_ticket", {"ticket_id": "790"}),
        ):
            negatives[name] = "UNKNOWN" if read({**request, **change}) is None else "ERROR"
        with self.psycopg.connect(self.db_url) as conn:
            conn.execute(
                "update public.ci_actor_source_grants set revoked=true "
                "where run_id=%s", (run,))
        negatives["revoked"] = "UNKNOWN" if read(request) is None else "ERROR"
        with self.psycopg.connect(self.db_url) as conn:
            conn.execute(
                "update public.ci_actor_source_grants set revoked=false,"
                "expires_at=clock_timestamp()-interval '1 second' "
                "where run_id=%s", (run,))
        negatives["expired"] = "UNKNOWN" if read(request) is None else "ERROR"
        self.assertEqual(negatives, {k: "UNKNOWN" for k in negatives})
        with self.psycopg.connect(self.db_url) as conn:
            conn.execute(
                "update public.ci_actor_source_grants "
                "set expires_at=clock_timestamp()+interval '3 minutes' "
                "where run_id=%s", (run,))
        self.assertIsNone(read(request, at=datetime.now(timezone.utc)
                               + timedelta(minutes=6)))
        self.assertIsNotNone(read(request))

        def audit(url):
            with self.psycopg.connect(url) as conn:
                return {
                    "nonce_013": conn.execute(
                        "select count(*) from aiops.actor_delegation_nonce_ledger"
                    ).fetchone()[0],
                    "revocation_013": conn.execute(
                        "select count(*) from aiops.actor_delegation_revocations"
                    ).fetchone()[0],
                    "terminal_014": conn.execute(
                        "select count(*) from aiops.hitl_reject_terminal_receipts"
                    ).fetchone()[0],
                }
        before = audit(self.db_url)
        with tempfile.TemporaryDirectory(prefix="core-written-015-") as tmp:
            dump = Path(tmp) / "backup.dump"
            restore_name = "aiops_core_written_015_restore_ci"
            restore_url = self.db_url.replace("/" + self.db_name,
                                              "/" + restore_name)
            with self.psycopg.connect(self.admin_url, autocommit=True) as conn:
                conn.execute(self.sql.SQL("create database {}").format(
                    self.sql.Identifier(restore_name)))
            try:
                subprocess.run(
                    ["/usr/lib/postgresql/16/bin/pg_dump", "--format=custom",
                     "--file", str(dump), "--dbname", self.db_url],
                    check=True, timeout=120, capture_output=True)
                archive_sha = hashlib.sha256(dump.read_bytes()).hexdigest()
                subprocess.run(
                    ["/usr/lib/postgresql/16/bin/pg_restore",
                     "--single-transaction", "--exit-on-error",
                     "--no-owner", "--no-acl", "--dbname", restore_url,
                     str(dump)],
                    check=True, timeout=120, capture_output=True)
                self.assertIsNotNone(read(request, db_url=restore_url))
                self.assertEqual(before, audit(restore_url))
                with self.psycopg.connect(restore_url) as conn:
                    self.assertEqual(conn.execute(
                        "select count(*) from aiops.run_events "
                        "where run_id=%s and event_key like 'SYN-EVT-%%'",
                        (run,)).fetchone()[0], 7)
                    self.assertEqual(conn.execute(
                        "select count(*) from pg_trigger where tgname in "
                        "('trg_actor_nonce_immutable',"
                        "'trg_actor_revocation_immutable',"
                        "'trg_hitl_reject_terminal_immutable') "
                        "and not tgisinternal").fetchone()[0], 3)
            finally:
                with self.psycopg.connect(self.admin_url, autocommit=True) as conn:
                    conn.execute(self.sql.SQL("drop database {} with (force)").format(
                        self.sql.Identifier(restore_name)))
        self.assertEqual(before, audit(self.db_url))
        out = os.environ.get("AIOPS_CORE_SEVEN_RECEIPT_DIR")
        if out:
            machine = {
                "schema": "aiops.core-written-seven-015-source-receipt.v1",
                "source_head": os.environ["AIOPS_EXPECTED_HEAD_SHA"],
                "installed": ["001", "004", "009", "010", "011",
                              "012", "013", "014", "015"],
                "producer": "core.canonical_seven_pg_source.read_core_written_seven",
                "writer": "core.main.app /api/runs/{rid}/events",
                "transport": "DISPOSABLE_TLS_BASIC_BOUND",
                "source_issuer_distinct_from_idp": True,
                "actor_subject_sha256": hashlib.sha256(actor.encode()).hexdigest(),
                "tenant_id": tenant, "incident_id": incident, "run_id": run,
                "decision": "UNKNOWN", "link_status": "UNKNOWN",
                "portable_signature": "NONE", "human_glpi_attested": False,
                "source_preflight": "PASS_SYNTHETIC_ONLY",
                "hash_domains": {
                    "payload": binding.PAYLOAD_DOMAIN,
                    "full_event": binding.FULL_DOMAIN,
                    "acme_full_event_equivalence": "NOT_VERIFIED",
                },
                "events": [{
                    "source_event_id": e["source_event_id"],
                    "payload_sha256": e["payload_hash"],
                    "full_event_sha256": e["full_event_hash"],
                } for e in proof["events"]],
                "negative_cases": negatives, "stale": "UNKNOWN",
                "audit_before": before, "audit_after": audit(self.db_url),
                "native_pg16_restore": True, "archive_sha256": archive_sha,
                "archive_retained": False, "release_stable": "NO_GO",
            }
            machine["receipt_sha256"] = hashlib.sha256(json.dumps(
                machine, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
            target = Path(out)
            target.mkdir(parents=True, exist_ok=True)
            (target / "core-written-seven-015.json").write_text(
                json.dumps(machine, sort_keys=True, indent=2) + "\n")


if __name__ == "__main__":
    unittest.main()
