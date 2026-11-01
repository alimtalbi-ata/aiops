"""Disposable PostgreSQL 16 canonical Core source authority: seven SHA256 events.

TEST_ONLY service and trust root. No production schema, GLPI, external network,
positive actor authorization or mutation of installed 013 audit records.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from pathlib import Path
import shutil
import ssl
import subprocess
import tempfile
import threading
import time
import unittest
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit, urlunsplit
from unittest.mock import patch

import requests

from core import actor_resource_authz, actor_run_event_source

MIG = Path(__file__).resolve().parents[1] / "db" / "migrations"
ORDER = ("001_schema.sql", "004_operational_model.sql", "009_ai_decision_ledger.sql",
         "010_evidence_identity.sql", "011_hitl_decision_outbox.sql",
         "012_itsm_xref_read.sql", "013_actor_delegation_replay_ledger.sql")
TENANT, RUN, INCIDENT, TICKET, ENTITY = "TEN-A", "RUN-A", "INC-A", "123", "7"
ISSUER, SUBJECT = "https://idp.synthetic.invalid", "idp|alice"
CLIENT, SECRET = "source-reader-disposable", "s" * 48
SOURCE = "CORE_CI_SYNTHETIC"
PORT = 8443
IP = "127.0.0.5"
SCHEMA = "aiops.core-source-event-payload.v1"


def canonical_hash(event):
    """Hash domain: SHA256(UTF8(JSON({schema,event}, sort_keys, compact, ASCII)))."""
    raw = json.dumps({"schema": SCHEMA, "event": event}, sort_keys=True,
                     separators=(",", ":"), ensure_ascii=True).encode("ascii")
    return hashlib.sha256(raw).hexdigest()


def event_at(i):
    return {"source_event_id": f"EVT-SOURCE-{i:02d}", "sequence": i,
            "tenant_id": TENANT, "incident_id": INCIDENT, "run_id": RUN,
            "ticket_id": TICKET, "glpi_entity_id": ENTITY,
            "metric": f"synthetic-signal-{i}", "synthetic": True}


def _now():
    return datetime.now(timezone.utc)


class SourceHandler(BaseHTTPRequestHandler):
    """Independent, Basic-authenticated, read-only SQL authority on real TLS."""

    def log_message(self, *_):
        pass

    def reply(self, status, payload):
        raw = json.dumps(payload, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_POST(self):
        import psycopg

        if self.path != "/v1/run-event-readback":
            return self.reply(404, {"status": "UNKNOWN"})
        token = "Basic " + base64.b64encode((CLIENT + ":" + SECRET).encode()).decode()
        if not hmac.compare_digest(self.headers.get("Authorization", ""), token):
            return self.reply(401, {"status": "UNKNOWN"})
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 1 <= length <= 8192:
                return self.reply(404, {"status": "UNKNOWN"})
            request = json.loads(self.rfile.read(length))
            if not isinstance(request, dict) or set(request) != set(actor_run_event_source._FIELDS):
                return self.reply(404, {"status": "UNKNOWN"})
            if any(not isinstance(v, str) or not v for v in request.values()):
                return self.reply(404, {"status": "UNKNOWN"})
            now = _now()
            with psycopg.connect(self.server.db_url) as conn:
                conn.execute("set transaction read only")
                grant = conn.execute(
                    "select expires_at,revoked from public.ci_actor_source_grants "
                    "where issuer=%s and actor_subject=%s and tenant_id=%s and run_id=%s "
                    "and incident_id=%s and glpi_instance_id=%s and ticket_id=%s "
                    "and glpi_entity_id=%s and permission=%s",
                    (ISSUER, request["actor_subject"], request["tenant_id"],
                     request["run_id"], request["incident_id"],
                     request["glpi_instance_id"], request["ticket_id"],
                     request["glpi_entity_id"], request["permission"])).fetchone()
                if not grant or grant[1] is not False or grant[0] <= now:
                    return self.reply(404, {"status": "UNKNOWN"})
                linked = conn.execute(
                    "select r.incident_id, i.incident_id from aiops.runs r "
                    "join aiops.incidents i on i.incident_id=r.incident_id "
                    "where r.run_id=%s and i.incident_id=%s and r.mode='DEMO' "
                    "and i.synthetic=true",
                    (request["run_id"], request["incident_id"])).fetchone()
                if linked != (INCIDENT, INCIDENT):
                    return self.reply(404, {"status": "UNKNOWN"})
                owned = conn.execute(
                    "select resource_kind,resource_id,tenant_id,verified,observed_at,known_at "
                    "from aiops.tenant_resource_ownership").fetchall()
                required = {("incident", INCIDENT), ("run", RUN),
                            ("glpi_instance", "GLPI-A"),
                            ("glpi_ticket", "GLPI-A:" + TICKET),
                            ("glpi_entity", "GLPI-A:" + ENTITY)}
                if (request["tenant_id"] != TENANT or
                        request["glpi_instance_id"] != "GLPI-A" or
                        {(k, rid) for k, rid, *_ in owned} != required or
                        any(t != TENANT or v is not True or
                            not now - timedelta(minutes=5) <= obs <= known <= now
                            for _, _, t, v, obs, known in owned)):
                    return self.reply(404, {"status": "UNKNOWN"})
                rows = conn.execute(
                    "select e.external_id,e.evidence_id,e.payload_hash,e.payload,"
                    "e.observed_at,e.known_at,r.sequence,r.evidence_ids,r.payload "
                    "from aiops.evidence e join aiops.run_events r "
                    "on r.run_id=%s and r.payload->>'source_event_id'=e.external_id "
                    "where e.source=%s and e.provenance->>'run_id'=%s "
                    "order by r.sequence",
                    (RUN, SOURCE, RUN)).fetchall()
                if len(rows) != 7:
                    return self.reply(404, {"status": "UNKNOWN"})
                matched = None
                for i, (event_id, evidence_id, digest, payload, observed, known,
                        sequence, evidence_ids, run_payload) in enumerate(rows, 1):
                    canonical = event_at(i)
                    if (sequence != i or event_id != canonical["source_event_id"]
                            or payload != canonical or run_payload != canonical
                            or evidence_ids != [evidence_id]
                            or digest != canonical_hash(canonical)
                            or not now - timedelta(minutes=5) <= observed <= known <= now):
                        return self.reply(404, {"status": "UNKNOWN"})
                    if event_id == request["source_event_id"]:
                        matched = (digest, observed, known)
                if matched is None or matched[0] != request["source_event_hash"]:
                    return self.reply(404, {"status": "UNKNOWN"})
            self.server.calls += 1
            return self.reply(200, {
                **request, "schema": actor_run_event_source.SCHEMA,
                "issuer": "core-source-disposable-authority",
                "source_system": "CORE_CANONICAL_READBACK",
                "observed_at": int(matched[1].timestamp()),
                "known_at": int(matched[2].timestamp()),
                "expires_at": int(min(grant[0], now + timedelta(seconds=60)).timestamp()),
                "revoked": False, "verified": True})
        except Exception:
            return self.reply(503, {"status": "UNKNOWN"})


@unittest.skipUnless(os.environ.get("AIOPS_XREF_CI_DISPOSABLE") == "1"
                     and os.environ.get("GITHUB_ACTIONS") == "true",
                     "dedicated disposable PostgreSQL 16 CI only")
class CanonicalSevenSourcePG16(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import psycopg
        from psycopg import sql
        cls.psycopg, cls.sql = psycopg, sql
        parsed = urlsplit(os.environ["DATABASE_URL"])
        if (parsed.scheme not in ("postgres", "postgresql") or
                parsed.hostname != "127.0.0.1" or parsed.port != 5432 or
                parsed.path != "/aiops" or parsed.username != "aiops" or
                parsed.query or parsed.fragment):
            raise RuntimeError("refuse non-disposable PostgreSQL")
        cls.admin_url = os.environ["DATABASE_URL"]
        cls.db_name = "aiops_core_source_seven_ci"
        cls.db_url = urlunsplit((parsed.scheme, parsed.netloc,
                                "/" + cls.db_name, "", ""))
        cls.created = False
        cls.root = tempfile.TemporaryDirectory(prefix="core-seven-tls-")
        try:
            with psycopg.connect(cls.admin_url, autocommit=True) as conn:
                version = int(conn.execute("show server_version_num").fetchone()[0])
                if not 160000 <= version < 170000:
                    raise RuntimeError("PostgreSQL 16 required")
                conn.execute(sql.SQL("create database {}").format(sql.Identifier(cls.db_name)))
                cls.created = True
            with psycopg.connect(cls.db_url) as conn:
                for name in ORDER:
                    conn.execute((MIG / name).read_text(encoding="utf-8"))
                now = _now()
                conn.execute(
                    "insert into aiops.incidents "
                    "(incident_id,title,severity,state,opened_at,source,synthetic) "
                    "values (%s,'Disposable canonical event','P3','OPEN',%s,%s,true)",
                    (INCIDENT, now-timedelta(seconds=60), SOURCE))
                conn.execute(
                    "insert into aiops.runs "
                    "(run_id,incident_id,mode,scenario_id,status,idempotency_key) "
                    "values (%s,%s,'DEMO','SCENARIO-CI','CREATED','source-ci-unique')",
                    (RUN, INCIDENT))
                for kind, rid in (("incident", INCIDENT), ("run", RUN),
                                  ("glpi_instance", "GLPI-A"),
                                  ("glpi_ticket", "GLPI-A:" + TICKET),
                                  ("glpi_entity", "GLPI-A:" + ENTITY)):
                    conn.execute(
                        "insert into aiops.tenant_resource_ownership "
                        "(resource_kind,resource_id,tenant_id,source_event_id,"
                        "verified,observed_at,known_at) "
                        "values (%s,%s,%s,'EVT-OWN-CI',true,%s,%s)",
                        (kind, rid, TENANT, now-timedelta(seconds=40),
                         now-timedelta(seconds=30)))
                for i in range(1, 8):
                    event = event_at(i)
                    evidence_id = f"EVIDENCE-SOURCE-{i:02d}"
                    conn.execute(
                        "insert into aiops.evidence "
                        "(evidence_id,source,external_id,observed_at,known_at,claim,"
                        "confidence,provenance,payload_hash,payload) "
                        "values (%s,%s,%s,%s,%s,'TEST_ONLY',1,%s::jsonb,%s,%s::jsonb)",
                        (evidence_id, SOURCE, event["source_event_id"],
                         now-timedelta(seconds=20), now-timedelta(seconds=10),
                         json.dumps({"tenant_id": TENANT, "run_id": RUN,
                                     "incident_id": INCIDENT}),
                         canonical_hash(event), json.dumps(event)))
                    conn.execute(
                        "insert into aiops.run_events "
                        "(event_id,run_id,sequence,stage,event_type,status,evidence_ids,payload) "
                        "values (%s,%s,%s,'SOURCE','OBSERVED','PASS',%s::jsonb,%s::jsonb)",
                        (f"RUN-EVT-{i:02d}", RUN, i,
                         json.dumps([evidence_id]), json.dumps(event)))
                # Disposable-only immutability fence. Not an installed migration.
                for table in ("evidence", "run_events"):
                    conn.execute(
                        f"create trigger ci_source_immutable before update or delete "
                        f"on aiops.{table} for each row "
                        f"execute function aiops.prevent_itsm_xref_mutation()")
                conn.execute(
                    "create table public.ci_actor_source_grants ("
                    "issuer text not null,actor_subject text not null,tenant_id text not null,"
                    "run_id text not null,incident_id text not null,glpi_instance_id text not null,"
                    "ticket_id text not null,glpi_entity_id text not null,permission text not null,"
                    "expires_at timestamptz not null,revoked boolean not null default false)")
                conn.execute(
                    "insert into public.ci_actor_source_grants values "
                    "(%s,%s,%s,%s,%s,'GLPI-A',%s,%s,'run:read',%s,false)",
                    (ISSUER, SUBJECT, TENANT, RUN, INCIDENT, TICKET, ENTITY,
                     now+timedelta(minutes=3)))
                hashval = lambda s: hashlib.sha256(s.encode()).hexdigest()
                self_hash = hashval("ci-source-nonce")
                conn.execute(
                    "select aiops.actor_delegation_consume(%s,%s,%s,%s,%s,%s,%s)",
                    (TENANT, ISSUER, hashval(SUBJECT), hashval("ci-source-jti"),
                     self_hash, hashval("ci-source-resource"),
                     now+timedelta(minutes=2)))
                conn.execute(
                    "select aiops.actor_delegation_revoke(%s,%s,%s)",
                    (ISSUER, hashval("ci-source-revoked-jti"), "REV-CI-SOURCE"))
            if not shutil.which("openssl"):
                raise RuntimeError("OpenSSL required; no TLS skip")
            root = Path(cls.root.name)
            def openssl(*args):
                subprocess.run(["openssl", *map(str, args)], check=True, timeout=20,
                               stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            openssl("req", "-x509", "-newkey", "rsa:2048", "-nodes",
                    "-sha256", "-days", "1", "-subj", "/CN=Core disposable CA",
                    "-addext", "basicConstraints=critical,CA:TRUE",
                    "-addext", "keyUsage=critical,keyCertSign,cRLSign",
                    "-keyout", root/"ca.key", "-out", root/"ca.pem")
            openssl("req", "-newkey", "rsa:2048", "-nodes",
                    "-subj", "/CN=Core source", "-keyout", root/"leaf.key",
                    "-out", root/"leaf.csr")
            (root/"leaf.ext").write_text(
                "subjectAltName=IP:127.0.0.5\nextendedKeyUsage=serverAuth\n"
                "keyUsage=digitalSignature,keyEncipherment\n", encoding="ascii")
            openssl("x509", "-req", "-in", root/"leaf.csr", "-CA", root/"ca.pem",
                    "-CAkey", root/"ca.key", "-CAcreateserial", "-out",
                    root/"leaf.pem", "-days", "1", "-sha256",
                    "-extfile", root/"leaf.ext")
        except Exception:
            cls.tearDownClass()
            raise

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "created", False):
            with cls.psycopg.connect(cls.admin_url, autocommit=True) as conn:
                conn.execute(cls.sql.SQL("drop database {} with (force)").format(
                    cls.sql.Identifier(cls.db_name)))
        if getattr(cls, "root", None):
            cls.root.cleanup()

    def setUp(self):
        self.now = int(time.time())
        self.expected = {"tenant_id": TENANT, "run_id": RUN, "incident_id": INCIDENT,
                         "glpi_instance_id": "GLPI-A", "ticket_id": TICKET,
                         "glpi_entity_id": ENTITY, "permission": "run:read",
                         "nonce": "nonce_disposable_01234567890123456789"}
        self.claims = {"sub": SUBJECT, "iss": ISSUER, "exp": self.now+120}
        self.server = ThreadingHTTPServer((IP, PORT), SourceHandler)
        self.server.daemon_threads = True
        self.server.db_url, self.server.calls = self.db_url, 0
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        root = Path(self.root.name)
        context.load_cert_chain(str(root/"leaf.pem"), str(root/"leaf.key"))
        self.server.socket = context.wrap_socket(self.server.socket, server_side=True)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        cfg = {"tenant_id": TENANT, "glpi_instance_id": "GLPI-A",
               "url": f"https://{IP}:{PORT}/v1/run-event-readback",
               "issuer": "core-source-disposable-authority",
               "client_id": CLIENT, "client_secret": SECRET}
        self.env = patch.dict(os.environ, {
            "AIOPS_XREF_ACTOR_CORE_SOURCE_JSON": json.dumps([cfg])})
        self.env.start()
        self.trust = patch("requests.adapters.DEFAULT_CA_BUNDLE_PATH",
                           str(root/"ca.pem"))
        self.trust.start()
        ca = ssl.create_default_context(cafile=str(root/"ca.pem"))
        self.preloaded = patch.object(requests.adapters, "_preloaded_ssl_context",
                                      ca, create=True)
        self.preloaded.start()

    def tearDown(self):
        self.preloaded.stop()
        self.trust.stop()
        self.env.stop()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)
        with self.psycopg.connect(self.db_url) as conn:
            conn.execute(
                "update public.ci_actor_source_grants set revoked=false,"
                "expires_at=clock_timestamp()+interval '3 minutes'")

    def read(self, i=1, expected=None, claims=None, record=None):
        event = event_at(i)
        row = {"run_id": RUN, "incident_id": INCIDENT,
               "glpi_entity_id": ENTITY, "source_event_id": event["source_event_id"],
               "source_payload_hash": canonical_hash(event)}
        return actor_run_event_source._source_run_event_preflight(
            self.claims if claims is None else claims,
            self.expected if expected is None else expected,
            row if record is None else record, int(time.time()))

    def test_all_seven_exact_canonical_hashes_independently_read(self):
        for i in range(1, 8):
            with self.subTest(event=i):
                self.assertTrue(self.read(i))
        self.assertEqual(self.server.calls, 7)
        self.assertEqual(json.loads(actor_resource_authz._reply().body)["decision"],
                         "UNKNOWN")

    def test_actor_tenant_run_incident_ticket_entity_permission_fail_closed(self):
        for changes in ({"tenant_id": "TEN-B"}, {"run_id": "RUN-B"},
                        {"incident_id": "INC-B"}, {"ticket_id": "124"},
                        {"glpi_entity_id": "8"}, {"permission": "ticket:write"}):
            with self.subTest(changes=changes):
                self.assertFalse(self.read(expected={**self.expected, **changes}))
        self.assertFalse(self.read(claims={**self.claims, "sub": "idp|bob"}))
        self.assertFalse(self.read(record={"run_id": RUN, "incident_id": INCIDENT,
                                          "glpi_entity_id": ENTITY,
                                          "source_event_id": "EVT-SOURCE-01",
                                          "source_payload_hash": "a"*64}))

    def test_revoked_and_expired_source_grant_fail_closed(self):
        with self.psycopg.connect(self.db_url) as conn:
            conn.execute("update public.ci_actor_source_grants set revoked=true")
        self.assertFalse(self.read())
        with self.psycopg.connect(self.db_url) as conn:
            conn.execute("update public.ci_actor_source_grants set revoked=false,"
                         "expires_at=clock_timestamp()-interval '1 second'")
        self.assertFalse(self.read())

    def test_seven_evidence_hashes_are_immutable_in_disposable_source(self):
        with self.psycopg.connect(self.db_url) as conn:
            self.assertEqual(conn.execute(
                "select count(*) from aiops.evidence where source=%s",
                (SOURCE,)).fetchone()[0], 7)
            with self.assertRaises(self.psycopg.Error):
                conn.execute("update aiops.evidence set payload_hash=%s "
                             "where external_id='EVT-SOURCE-01'", ("a"*64,))
            conn.rollback()
        with self.psycopg.connect(self.db_url) as conn:
            with self.assertRaises(self.psycopg.Error):
                conn.execute("delete from aiops.run_events where run_id=%s", (RUN,))
            conn.rollback()
        self.assertTrue(self.read(7))

    def test_tls_untrusted_ca_rejected_and_audit_013_unchanged(self):
        with self.psycopg.connect(self.db_url) as conn:
            before = (conn.execute(
                "select count(*) from aiops.actor_delegation_nonce_ledger").fetchone()[0],
                conn.execute(
                "select count(*) from aiops.actor_delegation_revocations").fetchone()[0])
        with patch("requests.adapters.DEFAULT_CA_BUNDLE_PATH", requests.certs.where()), \
             patch.object(requests.adapters, "_preloaded_ssl_context",
                          ssl.create_default_context(cafile=requests.certs.where()),
                          create=True):
            self.assertFalse(self.read())
        with self.psycopg.connect(self.db_url) as conn:
            after = (conn.execute(
                "select count(*) from aiops.actor_delegation_nonce_ledger").fetchone()[0],
                conn.execute(
                "select count(*) from aiops.actor_delegation_revocations").fetchone()[0])
        self.assertEqual(before, (1, 1))
        self.assertEqual(after, before)


if __name__ == "__main__":
    unittest.main()
