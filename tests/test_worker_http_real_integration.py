"""Actual loopback Worker HTTP -> actual Core HTTP/PostgreSQL 16 preflight.

Temporal dispatch is deliberately instrumented (not executed). No stage, gate,
Evidence, Twin or LIVE command is invoked. Only ephemeral CI database rows.
"""
import http.client
import json
import os
import socket
import threading
import time
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from urllib.parse import urlsplit

import psycopg
import requests
import uvicorn

from worker import main as worker_app


CORE = "http://127.0.0.1:1810"
TOKEN = os.environ.get("AIOPS_INTERNAL_TOKEN", "")
PREFIX = "CI-WORKER-HTTP-"


class InstrumentedTemporal:
    """Records dispatch only; never starts a workflow or a Temporal worker."""

    def __init__(self):
        self.calls = []

    async def start_workflow(self, workflow, args, *, id, task_queue):
        self.calls.append((args.copy(), id, task_queue))
        return SimpleNamespace(id=id)


class WorkerRealHTTPPreflight(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        url = urlsplit(os.environ.get("DATABASE_URL", ""))
        if (os.environ.get("AIOPS_REAL_WORKER_HTTP_CI") != "1"
                or url.hostname != "127.0.0.1" or url.port != 5432
                or not TOKEN.startswith("ci-noc-internal-ephemeral-")):
            raise RuntimeError("BLOCKED: only isolated loopback CI fixtures are allowed")

        cls.runs = {
            "CREATED": ("DEMO", "CREATED", 1),
            "LIVE": ("LIVE", "CREATED", 1),
            "RUNNING": ("DEMO", "RUNNING", 2),
            "BLOCKED": ("DEMO", "BLOCKED", 2),
        }
        with psycopg.connect(os.environ["DATABASE_URL"]) as db:
            for suffix, (mode, status, version) in cls.runs.items():
                db.execute(
                    "insert into aiops.runs(run_id,mode,scenario_id,status,"
                    "version,idempotency_key) values(%s,%s,%s,%s,%s,%s)",
                    ("RUN-" + PREFIX + suffix, mode, "CI-ACME", status,
                     version, PREFIX + suffix),
                )

        cls.temporal = InstrumentedTemporal()
        cls.connect = AsyncMock(return_value=cls.temporal)
        cls.client_patch = patch.object(
            worker_app, "Client", SimpleNamespace(connect=cls.connect))
        cls.client_patch.start()
        worker_app.CORE = CORE

        cls.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        cls.sock.bind(("127.0.0.1", 0))
        cls.sock.listen(128)
        cls.port = cls.sock.getsockname()[1]
        # Lifespan disabled: no background Temporal worker is started.
        cls.server = uvicorn.Server(uvicorn.Config(
            worker_app.app, host="127.0.0.1", port=cls.port,
            lifespan="off", log_level="error", access_log=False,
        ))
        cls.thread = threading.Thread(
            target=cls.server.run, kwargs={"sockets": [cls.sock]}, daemon=True)
        cls.thread.start()
        for _ in range(50):
            try:
                response = requests.get(cls.base() + "/health", timeout=0.5)
                if response.status_code == 200:
                    break
            except requests.RequestException:
                pass
            time.sleep(0.1)
        else:
            raise RuntimeError("BLOCKED: ephemeral Worker HTTP failed to start")

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "server"):
            cls.server.should_exit = True
            cls.thread.join(timeout=10)
            cls.sock.close()
        if hasattr(cls, "client_patch"):
            cls.client_patch.stop()
        if hasattr(cls, "runs"):
            with psycopg.connect(os.environ["DATABASE_URL"]) as db:
                db.execute("delete from aiops.runs where run_id like %s",
                           ("RUN-" + PREFIX + "%",))

    @classmethod
    def base(cls):
        return f"http://127.0.0.1:{cls.port}"

    def setUp(self):
        self.temporal.calls.clear()
        self.connect.reset_mock()
        self.core_patch = patch.object(
            worker_app, "get_json", wraps=worker_app.get_json)
        self.core_read = self.core_patch.start()

    def tearDown(self):
        self.core_patch.stop()

    @staticmethod
    def args(suffix="CREATED", **changes):
        payload = {
            "run_id": "RUN-" + PREFIX + suffix,
            "mode": "DEMO",
            "scenario_id": "CI-ACME",
            "version": 1,
        }
        payload.update(changes)
        return payload

    def post(self, payload, authorization=None):
        headers = {"Content-Type": "application/json"}
        if authorization is not None:
            headers["Authorization"] = authorization
        return requests.post(
            self.base() + "/api/execution/start", json=payload,
            headers=headers, timeout=5, allow_redirects=False,
        )

    def duplicate_header_post(self, headers):
        body = json.dumps(self.args()).encode("utf-8")
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        try:
            connection.putrequest("POST", "/api/execution/start")
            connection.putheader("Content-Type", "application/json")
            connection.putheader("Content-Length", str(len(body)))
            for value in headers:
                connection.putheader("Authorization", value)
            connection.endheaders(body)
            response = connection.getresponse()
            return response.status, response.read().decode("utf-8")
        finally:
            connection.close()

    def assert_no_dispatch_or_core_read(self):
        self.assertEqual(self.connect.await_count, 0)
        self.assertEqual(self.temporal.calls, [])
        self.assertEqual(self.core_read.call_count, 0)

    def test_real_http_health_is_not_temporal_readiness(self):
        response = requests.get(self.base() + "/health", timeout=5)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["component"], "worker")
        self.assert_no_dispatch_or_core_read()

    def test_real_http_rejects_missing_bare_and_malformed_bearer(self):
        for header in (None, TOKEN, "bearer " + TOKEN,
                       "Bearer  " + TOKEN, "Bearer " + TOKEN + " "):
            with self.subTest(header=repr(header)):
                response = self.post(self.args(), header)
                self.assertEqual(response.status_code, 401, response.text)
                self.assertNotIn(TOKEN, response.text)
                self.assert_no_dispatch_or_core_read()

    def test_real_http_rejects_duplicate_authorization_fields(self):
        for headers in (("Bearer " + TOKEN, "Basic invalid"),
                        ("Basic invalid", "Bearer " + TOKEN),
                        ("Bearer " + TOKEN, "Bearer " + TOKEN)):
            with self.subTest(count=len(headers), first=headers[0][:6]):
                status, body = self.duplicate_header_post(headers)
                self.assertEqual(status, 401, body)
                self.assertNotIn(TOKEN, body)
                self.assert_no_dispatch_or_core_read()

    def test_real_http_rejects_invalid_binding_before_core(self):
        for payload in (
            self.args(run_id="RUN-INVALID!"),
            self.args(version=True),
            self.args(version=0),
            self.args(mode="live"),
            self.args(scenario_id=""),
        ):
            with self.subTest(payload=payload):
                response = self.post(payload, "Bearer " + TOKEN)
                self.assertEqual(response.status_code, 422, response.text)
                self.assert_no_dispatch_or_core_read()

    def test_real_core_rejects_live_identity_and_non_created_runs(self):
        for payload in (self.args("LIVE"), self.args("RUNNING"),
                        self.args("BLOCKED"), self.args(version=2),
                        self.args(scenario_id="OTHER")):
            with self.subTest(payload=payload):
                response = self.post(payload, "Bearer " + TOKEN)
                self.assertEqual(response.status_code, 409, response.text)
                self.assertEqual(self.connect.await_count, 0)
                self.assertEqual(self.temporal.calls, [])
        self.assertEqual(self.core_read.call_count, 5)

    def test_real_core_missing_run_fails_closed_without_temporal(self):
        response = self.post(self.args("MISSING"), "Bearer " + TOKEN)
        self.assertEqual(response.status_code, 503, response.text)
        self.assertEqual(self.core_read.call_count, 1)
        self.assertEqual(self.connect.await_count, 0)
        self.assertEqual(self.temporal.calls, [])

    def test_matching_demo_dispatch_is_instrumented_and_read_only(self):
        payload = self.args()
        response = self.post(payload, "Bearer " + TOKEN)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json(), {
            "workflow_id": payload["run_id"], "run_id": payload["run_id"],
            "executor": "temporal",
        })
        self.assertEqual(self.core_read.call_count, 1)
        self.assertEqual(self.connect.await_count, 1)
        self.assertEqual(self.temporal.calls, [
            (payload, payload["run_id"], "aiops-runner"),
        ])
        with psycopg.connect(os.environ["DATABASE_URL"]) as db:
            run = db.execute(
                "select status,version from aiops.runs where run_id=%s",
                (payload["run_id"],),
            ).fetchone()
            gates = db.execute(
                "select count(*) from aiops.gates where run_id=%s",
                (payload["run_id"],),
            ).fetchone()[0]
            events = db.execute(
                "select count(*) from aiops.run_events where run_id=%s",
                (payload["run_id"],),
            ).fetchone()[0]
        self.assertEqual(run, ("CREATED", 1))
        self.assertEqual((gates, events), (0, 0))


if __name__ == "__main__":
    unittest.main()
