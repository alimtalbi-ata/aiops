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
    """A separate service identity and read-only SQL transaction, not HMAC rows."""

    def do_POST(self):
        if self.path != "/v2/canonical-seven-readback":
            return super().do_POST()
        token = "Basic " + base64.b64encode(
            (fixture.CLIENT + ":" + fixture.SECRET).encode()).decode()
        if not hmac.compare_digest(self.headers.get("Authorization", ""), token):
            return self.reply(401, {"decision": "UNKNOWN"})
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 1 <= length <= 8192:
                return self.reply(404, {"decision": "UNKNOWN"})
            request = json.loads(self.rfile.read(length))
            if (not isinstance(request, dict) or set(request) != set(binding._SCOPE)
                    or any(type(v) is not str or not v for v in request.values())
                    or request["permission"] != "run:read"):
                return self.reply(404, {"decision": "UNKNOWN"})
            import psycopg
            now = datetime.now(timezone.utc)
            with psycopg.connect(self.server.db_url) as conn:
                conn.execute("set transaction read only")
                grant = conn.execute(
                    "select expires_at,revoked from public.ci_actor_source_grants "
                    "where issuer=%s and actor_subject=%s and tenant_id=%s "
                    "and run_id=%s and incident_id=%s and glpi_instance_id=%s "
                    "and ticket_id=%s and glpi_entity_id=%s and permission=%s",
                    (request["actor_issuer"], request["actor_subject"], request["tenant_id"],
                     request["run_id"], request["incident_id"],
                     request["glpi_instance_id"], request["ticket_id"],
                     request["glpi_entity_id"], request["permission"])).fetchone()
                if not grant or grant[1] is not False or grant[0] <= now:
                    return self.reply(404, {"decision": "UNKNOWN"})
                linked = conn.execute(
                    "select r.run_id,r.incident_id,i.synthetic "
                    "from aiops.runs r join aiops.incidents i "
                    "on i.incident_id=r.incident_id "
                    "where r.run_id=%s and r.incident_id=%s and r.mode='DEMO'",
                    (request["run_id"], request["incident_id"])).fetchone()
                if linked != (fixture.RUN, fixture.INCIDENT, True):
                    return self.reply(404, {"decision": "UNKNOWN"})
                ownership = conn.execute(
                    "select resource_kind,resource_id,tenant_id,verified,observed_at,known_at "
                    "from aiops.tenant_resource_ownership").fetchall()
                required = {("incident", fixture.INCIDENT),
                            ("run", fixture.RUN), ("glpi_instance", "GLPI-A"),
                            ("glpi_ticket", "GLPI-A:" + fixture.TICKET),
                            ("glpi_entity", "GLPI-A:" + fixture.ENTITY)}
                if ({(k, rid) for k, rid, *_ in ownership} != required
                        or request["tenant_id"] != fixture.TENANT
                        or request["glpi_instance_id"] != "GLPI-A"
                        or any(t != fixture.TENANT or v is not True
                               or not now-timedelta(minutes=5) <= obs <= known <= now
                               for _, _, t, v, obs, known in ownership)):
                    return self.reply(404, {"decision": "UNKNOWN"})
                rows = conn.execute(
                    "select e.external_id,e.evidence_id,e.payload_hash,e.payload,"
                    "e.observed_at,e.known_at,r.event_id,r.sequence,r.stage,"
                    "r.event_type,r.status,r.payload,r.evidence_ids "
                    "from aiops.evidence e join aiops.run_events r "
                    "on r.run_id=%s and r.payload->>'source_event_id'=e.external_id "
                    "where e.source=%s and e.provenance->>'run_id'=%s "
                    "order by r.sequence",
                    (request["run_id"], fixture.SOURCE, request["run_id"])).fetchall()
                if len(rows) != 7:
                    return self.reply(404, {"decision": "UNKNOWN"})
                events = []
                for pos, row in enumerate(rows, 1):
                    (source_id, evidence_id, payload_hash, payload, observed, known,
                     event_id, sequence, stage, event_type, status,
                     run_payload, evidence_ids) = row
                    if (sequence != pos or payload != run_payload
                            or evidence_ids != [evidence_id]
                            or source_id != payload.get("source_event_id")
                            or payload.get("sequence") != pos
                            or payload_hash != binding._digest(binding.PAYLOAD_DOMAIN, payload)
                            or not now-timedelta(minutes=5) <= observed <= known <= now):
                        return self.reply(404, {"decision": "UNKNOWN"})
                    full = {"event_id": event_id, "run_id": request["run_id"],
                            "incident_id": request["incident_id"],
                            "tenant_id": request["tenant_id"], "sequence": sequence,
                            "stage": stage, "event_type": event_type, "status": status,
                            "evidence_id": evidence_id, "source_event_id": source_id,
                            "source_payload_hash": payload_hash,
                            "observed_at": int(observed.timestamp()),
                            "known_at": int(known.timestamp())}
                    events.append({
                        "sequence": sequence, "source_event_id": source_id,
                        "evidence_id": evidence_id, "payload": payload,
                        "payload_hash": payload_hash, "full_event": full,
                        "full_event_hash": binding._digest(binding.FULL_DOMAIN, full)})
            proof = {**request, "schema": binding.SCHEMA,
                     "issuer": "core-source-disposable-authority",
                     "source_system": "CORE_CANONICAL_READBACK",
                     "observed_at": int(rows[0][4].timestamp()),
                     "known_at": int(rows[-1][5].timestamp()),
                     "expires_at": int(min(grant[0], now + timedelta(seconds=60)).timestamp()),
                     "revoked": False, "events": events}
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


if __name__ == "__main__":
    unittest.main()
