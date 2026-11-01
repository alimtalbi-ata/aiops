"""Disposable PG16/Core/Policy/Temporal vertical REJECT-to-VERIFY regression.

Only synthetic fixtures and Core-owned terminal API; no LIVE, GLPI write,
SQL DEAD, immutable 012/013/014 mutation, or real human identity.
"""
import asyncio
import copy
import hashlib
import json
import os
import secrets
import socket
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

import test_worker_core_pg16_temporal_combined as base
import test_worker_core_dead_positive_pg16 as positive
from test_worker_hitl_reject_notification import SyntheticRejectSink
from policy.main import Decision, evaluate
from worker.hitl_reject_vertical_projection import (
    UnqualifiedRejectStory, project_rejected_simulation,
)


@unittest.skipUnless(
    os.getenv("GITHUB_ACTIONS") == "true"
    and os.getenv("AIOPS_CI_COMBINED_DISPOSABLE") == "YES"
    and os.getenv("AIOPS_CI_CORE_DEAD_POSITIVE") == "YES"
    and os.getenv("AIOPS_CI_VERTICAL_REJECT") == "YES",
    "isolated PG16 + Temporal CI only",
)
class WorkerRejectVerticalPG16(positive.CoreDeadPositiveWorkerContract):
    # Base owns PG16 migration setup and synthetic immutable fixture. No
    # historical SQL-injected DEAD tests or inherited base.setUp are run.
    for _old in dir(positive.CoreDeadPositiveWorkerContract):
        if _old.startswith("test_"):
            locals()[_old] = None
    del _old

    @classmethod
    def setUpClass(cls):
        # Core 015 is now part of the combined disposable candidate contract.
        # Install it after inherited 001/004/009-014, never on Debian.
        # This intentionally makes both conditional tests exercise real Core
        # HTTP writes; fixture-only fallback is no longer a green release gate.
        super().setUpClass()
        try:
            with cls.psycopg.connect(cls.url) as db:
                db.execute((base.ROOT / "db/migrations" /
                            "015_core_run_event_idempotency.sql").read_text())
                assert db.execute(
                    "select count(*) from information_schema.columns "
                    "where table_schema='aiops' and table_name='run_events' "
                    "and column_name='event_key'").fetchone()[0] == 1
        except Exception:
            super().tearDownClass()
            raise

    def setUp(self):
        pass

    async def test_15_core_analyst_critic_policy_reject_verify_correlation(self):
        head = os.environ["AIOPS_EXPECTED_HEAD_SHA"]
        self.assertEqual(len(head), 40)
        terminal_authz = json.dumps([{
            "token_sha256": hashlib.sha256(self.bearer.encode()).hexdigest(),
            "actor_id": base.OWNER, "tenant_ids": [base.TENANT],
            "permissions": ["hitl:reject:deliver", "hitl:reject:terminal"],
        }])
        admin = secrets.token_urlsafe(40)
        with patch.dict(os.environ, {
            "DATABASE_URL": self.url,
            "AIOPS_INTERNAL_TOKEN": admin,
            "AIOPS_XREF_READ_AUTHZ_JSON": terminal_authz,
        }):
            from core import main as core_main
            with patch.object(core_main, "ADMIN", admin):
                ids = self._fixture()
                self._write_synthetic_proofs()
                lease = None
                for attempt in range(8):
                    code, claim = self._claim()
                    self.assertEqual((code, claim["status"]), (200, "LEASED"))
                    self.assertEqual(len(claim["items"]), 1)
                    lease = claim["items"][0]
                    self.assertEqual(lease["event_id"], ids["event"])
                    self.assertEqual(lease["decision"], "REJECT")
                    self.assertIs(lease["execution_allowed"], False)
                    self.assertIs(lease["effect_allowed"], False)
                    # CI lease-clock acceleration only; never SQL-write DEAD.
                    with self.psycopg.connect(self.url) as db:
                        db.execute(
                            "update aiops.hitl_decision_outbox "
                            "set lease_until=now()-interval '2 seconds' "
                            "where event_id=%s and status='LEASED'",
                            (ids["event"],))
                terminal_path = (
                    f"/api/tenants/{base.TENANT}/hitl/"
                    f"reject-delivery/{ids['event']}/dead")
                terminal_body = {
                    "owner": base.OWNER, "run_id": ids["run"],
                    "proposal_id": ids["proposal"],
                    "proposal_hash": lease["proposal_hash"],
                    "proposal_revision": lease["proposal_revision"],
                    "lease_token": lease["lease_token"],
                    "execution_allowed": False, "effect_allowed": False,
                }
                code, dead = self._http(terminal_path, terminal_body)
                self.assertEqual((code, dead["status"], dead["idempotent"]),
                                 (200, "DEAD", False))
                code, replay = self._http(terminal_path, terminal_body)
                self.assertEqual((code, replay["status"], replay["idempotent"]),
                                 (200, "DEAD", True))
                self.assertEqual(self._claim()[1]["items"], [])

                policy = evaluate(Decision(
                    mode="DEMO", command="ENRICH", severity="P4",
                    confidence=0.5, evidence_count=1,
                    critic_validated=True, redundancy_ok=False))
                self.assertEqual((policy["state"], policy["decision"]),
                                 ("PASS", "SIMULATE"))
                self.assertIs(policy["execution_allowed"], False)
                self.assertIs(policy["effect_allowed"], False)

                # Existing Core API is the sole Run/event/gate writer. This
                # synthetic fixture uses no Portal/GLPI or executor route.
                with TestClient(core_main.app) as client:
                    headers = {"Authorization": "Bearer " + admin}
                    def post(route, payload):
                        response = client.post(route, json=payload, headers=headers)
                        self.assertEqual(response.status_code, 200, response.text)
                        return response.json()

                    route = f"/api/runs/{ids['run']}"
                    run = client.get(route).json()["run"]
                    self.assertEqual(run["incident_id"], ids["inc"])
                    # Core owns Run writes. The missing event_key migration
                    # forces a fixture-only negative path; NEVER call it E2E.
                    # Once the Core owner installs the full schema, exercise
                    # real HTTP writes, replay and BLOCK, without SQL events.
                    with self.psycopg.connect(self.url) as db:
                        has_event_key = db.execute(
                            "select exists(select 1 from "
                            "information_schema.columns "
                            "where table_schema='aiops' "
                            "and table_name='run_events' "
                            "and column_name='event_key')").fetchone()[0]
                    stages = [
                        ("DGX_ANALYST", "ANALYST_RECORDED", "analysis_id",
                         "PASS", None, {}),
                        ("DGX_CRITIC", "CRITIC_RECORDED", "critique_id",
                         "PASS", None, {}),
                        ("POLICY", "POLICY_EVALUATED", "proposal_id",
                         "PASS", "SIMULATE", {"policy_state": "PASS"}),
                        ("HITL", "HUMAN_REJECT_SYNTHETIC", "approval_id",
                         "BLOCKED", "REJECT", {"identity_attested": False}),
                        ("REMEDIATE", "SIMULATE_SUPPRESSED", "proposal_id",
                         "BLOCKED", "REJECT", {"simulation_executed": False}),
                        ("VERIFY", "VERIFY_UNRESOLVED", "proposal_id",
                         "BLOCKED", "REJECT",
                         {"resolution_verified": False,
                          "reopen_recommended": True}),
                    ]
                    if has_event_key:
                        start_command = {
                            "expected_version": run["version"],
                            "idempotency_key": "ci-vertical-start-" + ids["run"],
                            "command": "START",
                        }
                        started = post(route + "/command", start_command)
                        self.assertEqual(started["status"], "RUNNING")
                        self.assertEqual(
                            post(route + "/command", start_command), started)
                        version = started["version"]
                        for seq, (stage, event_type, binding, status,
                                  decision, extra) in enumerate(stages, 1):
                            payload = {
                                binding: ids[binding.removesuffix("_id")],
                                "tenant_id": base.TENANT,
                                "run_id": ids["run"],
                                "synthetic": True,
                                "execution_allowed": False,
                                "effect_allowed": False, **extra,
                            }
                            body = {
                                "expected_version": version,
                                "stage": stage, "event_type": event_type,
                                "status": status,
                                "event_key": "ci-vertical-" + str(seq)
                                             + "-" + ids["run"],
                                "evidence_ids": [ids["evidence"]],
                                "decision": decision, "payload": payload,
                            }
                            written = post(route + "/events", body)
                            self.assertIs(written["idempotent"], False)
                            version = written["version"]
                            replay = post(route + "/events",
                                          dict(body, expected_version=version))
                            self.assertIs(replay["idempotent"], True)
                            self.assertEqual(replay["version"], version)
                        block_command = {
                            "expected_version": version,
                            "idempotency_key": "ci-vertical-block-" + ids["run"],
                            "command": "BLOCK",
                        }
                        blocked = post(route + "/command", block_command)
                        self.assertEqual(blocked["status"], "BLOCKED")
                        self.assertEqual(
                            post(route + "/command", block_command), blocked)
                        self.assertEqual(
                            len(client.get(route).json()["events"]), 8)
                        core_event_write = "CORE_WRITTEN_PG16_OBSERVED"
                        run_events_source = "CORE_HTTP_WRITER_PG16"
                    else:
                        # CI mutable fixture only; no Core event write claim.
                        with self.psycopg.connect(self.url) as db:
                            for seq, (stage, event_type, binding, status,
                                      decision, extra) in enumerate(stages, 1):
                                payload = {
                                    binding: ids[binding.removesuffix("_id")],
                                    "tenant_id": base.TENANT,
                                    "run_id": ids["run"],
                                    "synthetic": True,
                                    "execution_allowed": False,
                                    "effect_allowed": False, **extra,
                                }
                                db.execute(
                                    "insert into aiops.run_events "
                                    "(event_id,run_id,sequence,stage,event_type,"
                                    "status,evidence_ids,decision,payload) "
                                    "values(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                                    ("CI-VERTICAL-EVT-" + str(seq)
                                     + "-" + ids["run"],
                                     ids["run"], seq, stage, event_type, status,
                                     json.dumps([ids["evidence"]]), decision,
                                     json.dumps(payload)))
                            db.execute(
                                "update aiops.runs set status='BLOCKED' "
                                "where run_id=%s and mode='DEMO'",
                                (ids["run"],))
                        core_event_write = "NOT_TESTED_MISSING_EVENT_KEY_MIGRATION"
                        run_events_source = "CI_PG16_FIXTURE_ONLY"
                    post(route + "/gates", {
                        "stage": "POLICY", "state": "PASS",
                        "decision": "SIMULATE",
                        "reason": "synthetic advisory; HITL REJECT veto",
                        "evidence_ids": [ids["evidence"]],
                        "required_evidence": ["analyst", "critic"]})
                    # Replayed gate is an idempotent Core upsert; it must
                    # remain one row and never grant an effect.
                    post(route + "/gates", {
                        "stage": "POLICY", "state": "PASS",
                        "decision": "SIMULATE",
                        "reason": "synthetic advisory; HITL REJECT veto",
                        "evidence_ids": [ids["evidence"]],
                        "required_evidence": ["analyst", "critic"]})
                    core_view = client.get(route).json()
                    self.assertEqual(core_view["run"]["status"], "BLOCKED")
                    self.assertEqual(core_view["run"]["incident_id"], ids["inc"])

                # Core-owned PostgreSQL 014 receipt is immutable and singular.
                with self.psycopg.connect(self.url) as db:
                    terminal = db.execute(
                        "select receipt_payload,receipt_sha256 "
                        "from aiops.hitl_reject_terminal_receipts "
                        "where event_id=%s", (ids["event"],)).fetchall()
                    self.assertEqual(len(terminal), 1)
                    payload, digest = terminal[0]
                    canonical = json.dumps(
                        payload, sort_keys=True, separators=(",", ":"),
                        ensure_ascii=True).encode()
                    self.assertEqual(hashlib.sha256(canonical).hexdigest(), digest)
                    self.assertIs(payload["execution_allowed"], False)
                    self.assertIs(payload["effect_allowed"], False)
                    ownership = db.execute(
                        "select tenant_id,verified from "
                        "aiops.tenant_resource_ownership "
                        "where resource_kind='run' and resource_id=%s",
                        (ids["run"],)).fetchall()
                    self.assertEqual(ownership, [(base.TENANT, True)])
                    incident = db.execute(
                        "select state,synthetic from aiops.incidents "
                        "where incident_id=%s", (ids["inc"],)).fetchone()
                    self.assertEqual(incident, ("OPEN", True))
                    analysis = db.execute(
                        "select status from aiops.analysis_records "
                        "where analysis_id=%s", (ids["analysis"],)).fetchone()
                    critic = db.execute(
                        "select validated from aiops.critique_records "
                        "where critique_id=%s", (ids["critique"],)).fetchone()
                    proposal = db.execute(
                        "select status,proposal_hash,proposal_revision "
                        "from aiops.action_proposals where proposal_id=%s",
                        (ids["proposal"],)).fetchone()
                    approval = db.execute(
                        "select decision,actor_id,audit from "
                        "aiops.approval_records where approval_id=%s",
                        (ids["approval"],)).fetchone()
                    outbox = db.execute(
                        "select status,decision from "
                        "aiops.hitl_decision_outbox where event_id=%s",
                        (ids["event"],)).fetchone()
                    self.assertEqual(outbox, ("DEAD", "REJECT"))
                    self.assertEqual(approval[0:2],
                                     ("REJECT", "SYNTHETIC_UNVERIFIED"))
                    self.assertIs(approval[2]["identity_attested"], False)
                    self.assertEqual(proposal[0], "REJECTED")
                    self.assertEqual(analysis, ("VALID",))
                    self.assertEqual(critic, (True,))

                ledger = {
                    "tenant_id": base.TENANT,
                    "incident_id": ids["inc"], "run_id": ids["run"],
                    "analysis_id": ids["analysis"],
                    "critique_id": ids["critique"],
                    "proposal_id": ids["proposal"],
                    "approval_id": ids["approval"], "event_id": ids["event"],
                    "evidence_id": ids["evidence"],
                    "proposal_hash": proposal[1],
                    "proposal_revision": proposal[2],
                    "analysis_status": analysis[0],
                    "critic_validated": critic[0],
                    "proposal_status": proposal[0],
                    "approval_decision": approval[0],
                    "actor_identity": approval[1],
                    "identity_attested": approval[2]["identity_attested"],
                    "outbox_decision": outbox[1],
                    "terminal_status": outbox[0],
                    "terminal_audit_rows": len(terminal),
                    "terminal_receipt_sha256": digest,
                    "tenant_provenance": "CI_SIGNED_PROOF_ONLY",
                    "incident_state": incident[0],
                    "synthetic": incident[1],
                }
                projection = project_rejected_simulation(core_view, ledger, policy)
                self.assertEqual(projection["simulation_status"],
                                 "SUPPRESSED_BY_REJECT")
                self.assertEqual(projection["reopen_status"],
                                 "RECOMMENDED_NOT_EXECUTED")
                for change in (
                    ("ledger", "tenant_id", "TEN-FOREIGN"),
                    ("ledger", "run_id", "RUN-FOREIGN"),
                    ("ledger", "proposal_hash", "bad"),
                    ("ledger", "proposal_revision", True),
                    ("ledger", "approval_decision", "APPROVE"),
                    ("ledger", "terminal_status", "LEASED"),
                    ("policy", "effect_allowed", True),
                    ("policy", "decision", "ALLOW"),
                ):
                    which, key, value = change
                    bad_ledger, bad_policy = copy.deepcopy(ledger), copy.deepcopy(policy)
                    (bad_ledger if which == "ledger" else bad_policy)[key] = value
                    with self.subTest(change=change), self.assertRaises(
                            UnqualifiedRejectStory):
                        project_rejected_simulation(core_view, bad_ledger, bad_policy)
                forged = copy.deepcopy(core_view)
                forged["events"] = [e for e in forged["events"]
                                    if e.get("event_type") != "VERIFY_UNRESOLVED"]
                with self.assertRaises(UnqualifiedRejectStory):
                    project_rejected_simulation(forged, ledger, policy)

                # Two separate disposable SDK Worker instances, same Temporal
                # task queue, after actual Temporal server SQLite restart.
                # No signal is emitted; the workflow history remains unchanged.
                def free_port():
                    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                        sock.bind(("127.0.0.1", 0))
                        return sock.getsockname()[1]

                queue = "ci-vertical-reject-" + secrets.token_hex(8)
                sqlite = str(Path(self.temp.name) / (queue + ".sqlite"))
                async with await WorkflowEnvironment.start_local(
                        port=free_port(),
                        dev_server_database_filename=sqlite) as temporal:
                    handle = await temporal.client.start_workflow(
                        SyntheticRejectSink.run, id=queue, task_queue=queue)
                    async with Worker(temporal.client, task_queue=queue,
                                      workflows=[SyntheticRejectSink]):
                        self.assertEqual(
                            await handle.query(SyntheticRejectSink.count), 0)
                async with await WorkflowEnvironment.start_local(
                        port=free_port(),
                        dev_server_database_filename=sqlite) as restarted:
                    handle = restarted.client.get_workflow_handle(queue)
                    async with Worker(restarted.client, task_queue=queue,
                                      workflows=[SyntheticRejectSink]) as worker_a:
                        async with Worker(restarted.client, task_queue=queue,
                                          workflows=[SyntheticRejectSink]) as worker_b:
                            self.assertIsNot(worker_a, worker_b)
                            projections = await asyncio.gather(
                                asyncio.to_thread(project_rejected_simulation,
                                                  core_view, ledger, policy),
                                asyncio.to_thread(project_rejected_simulation,
                                                  core_view, ledger, policy))
                            self.assertEqual(projections, [projection, projection])
                            self.assertEqual(
                                await handle.query(SyntheticRejectSink.count), 0)
                with self.psycopg.connect(self.url) as db:
                    after = db.execute(
                        "select receipt_sha256 from "
                        "aiops.hitl_reject_terminal_receipts where event_id=%s",
                        (ids["event"],)).fetchall()
                    self.assertEqual(after, [(digest,)])
                    self.assertEqual(db.execute(
                        "select count(*) from aiops.approval_records "
                        "where decision='APPROVE' and proposal_id=%s",
                        (ids["proposal"],)).fetchone()[0], 0)
                    self.assertEqual(db.execute(
                        "select count(*) from aiops.hitl_decision_outbox "
                        "where event_id=%s and status='DELIVERED'",
                        (ids["event"],)).fetchone()[0], 0)
                    self.assertEqual(db.execute(
                        "select state from aiops.incidents "
                        "where incident_id=%s", (ids["inc"],)).fetchone()[0],
                        "OPEN")
                receipt = {
                    **projection,
                    "source_head": head,
                    "core_run_api": ("CORE_HTTP_WRITER_AND_READBACK_OBSERVED"
                                     if has_event_key else
                                     "READ_ONLY_CORE_ASGI_OBSERVED"),
                    "core_event_write": core_event_write,
                    "run_events_source": run_events_source,
                    "core_terminal_api": "CORE_OWNED_DEAD_OBSERVED",
                    "migration_014": "ONE_IMMUTABLE_RECEIPT_OBSERVED",
                    "temporal_persisted_restarts": 1,
                    "disposable_worker_instances": 2,
                    "independent_os_processes": False,
                    "temporal_signal_count": 0,
                    "approve_count": 0, "effect_receipt_count": 0,
                    "live_executor_calls": 0, "glpi_write_calls": 0,
                    "sql_dead_injection": False,
                    "oidc_glpi_identity": "NOT_ATTESTED",
                    "physical_packet_loss": "NOT_TESTED",
                    "host_7777_local_operator": "REPORTED_VERIFIED",
                    "host_7777_external": "NOT_ATTESTED",
                    "universal_exactly_once": "NOT_CLAIMED",
                }
                canonical = json.dumps(
                    receipt, sort_keys=True, separators=(",", ":")).encode()
                receipt["payload_sha256"] = hashlib.sha256(canonical).hexdigest()
                target = Path(os.environ["AIOPS_CI_VERTICAL_REJECT_RECEIPT_DIR"])
                self.assertTrue(str(target).startswith("/tmp/hitl-worker-vertical-"))
                target.mkdir(parents=True, exist_ok=True)
                (target / "worker-vertical-reject.json").write_text(
                    json.dumps(receipt, sort_keys=True, indent=2) + "\n")


    async def test_16_core_event_command_writer_rollback_gate(self):
        """Probe the real Core writer without pretending fixture SQL is Core history.

        When 001/004/009-014 lacks event_key, both writes must leave the
        synthetic Run unchanged. When Core installs that column, require
        positive, idempotent writer behavior instead of silently passing an
        obsolete expected-500 assertion. No Core migration is owned here.
        """
        head = os.environ["AIOPS_EXPECTED_HEAD_SHA"]
        self.assertEqual(len(head), 40)
        ids = self._fixture()
        admin = secrets.token_urlsafe(40)
        with patch.dict(os.environ, {
            "DATABASE_URL": self.url, "AIOPS_INTERNAL_TOKEN": admin,
        }):
            from core import main as core_main
            with patch.object(core_main, "ADMIN", admin):
                with TestClient(core_main.app,
                                raise_server_exceptions=False) as client:
                    route = f"/api/runs/{ids['run']}"
                    before_response = client.get(route)
                    self.assertEqual(before_response.status_code, 200)
                    before = before_response.json()
                    self.assertEqual(before["run"]["status"], "CREATED")
                    self.assertEqual(before["events"], [])
                    version = before["run"]["version"]
                    headers = {"Authorization": "Bearer " + admin}
                    with self.psycopg.connect(self.url) as db:
                        has_event_key = db.execute(
                            "select exists(select 1 from "
                            "information_schema.columns "
                            "where table_schema='aiops' "
                            "and table_name='run_events' "
                            "and column_name='event_key')").fetchone()[0]
                        before_commands = db.execute(
                            "select count(*) from aiops.command_receipts "
                            "where run_id=%s", (ids["run"],)).fetchone()[0]
                    self.assertEqual(before_commands, 0)

                    event_body = {
                        "expected_version": version,
                        "stage": "POLICY",
                        "event_type": "POLICY_EVALUATED",
                        "status": "PASS",
                        "event_key": "ci-writer-gate",
                        "evidence_ids": [],
                        "decision": "SIMULATE",
                        "payload": {
                            "synthetic": True,
                            "execution_allowed": False,
                            "effect_allowed": False,
                        },
                    }
                    unauthorized = client.post(
                        route + "/events", json=event_body,
                        headers={"Authorization": "Bearer invalid"})
                    self.assertEqual(unauthorized.status_code, 401)
                    event_response = client.post(
                        route + "/events", json=event_body, headers=headers)
                    if has_event_key:
                        self.assertEqual(event_response.status_code, 200)
                        event_result = event_response.json()
                        self.assertIs(event_result["idempotent"], False)
                        replay_body = dict(
                            event_body, expected_version=event_result["version"])
                        replay = client.post(
                            route + "/events", json=replay_body,
                            headers=headers)
                        self.assertEqual(replay.status_code, 200)
                        self.assertIs(replay.json()["idempotent"], True)
                        command_version = event_result["version"]
                    else:
                        self.assertEqual(event_response.status_code, 500)
                        command_version = version

                    command_body = {
                        "expected_version": command_version,
                        "idempotency_key": "ci-writer-gate-start",
                        "command": "START",
                    }
                    command_response = client.post(
                        route + "/command", json=command_body,
                        headers=headers)
                    if has_event_key:
                        self.assertEqual(command_response.status_code, 200)
                        command_result = command_response.json()
                        self.assertEqual(command_result["status"], "RUNNING")
                        replay_command = client.post(
                            route + "/command",
                            json=dict(command_body,
                                      expected_version=command_result["version"]),
                            headers=headers)
                        self.assertEqual(replay_command.status_code, 200)
                        self.assertEqual(replay_command.json(), command_result)
                        writer_status = "CORE_WRITER_IDEMPOTENT_OBSERVED"
                    else:
                        self.assertEqual(command_response.status_code, 500)
                        writer_status = "BLOCKED_MISSING_EVENT_KEY_MIGRATION"

                    after_response = client.get(route)
                    self.assertEqual(after_response.status_code, 200)
                    after = after_response.json()
                    with self.psycopg.connect(self.url) as db:
                        commands = db.execute(
                            "select count(*) from aiops.command_receipts "
                            "where run_id=%s", (ids["run"],)).fetchone()[0]
                        terminal = db.execute(
                            "select count(*) from "
                            "aiops.hitl_reject_terminal_receipts t "
                            "join aiops.hitl_decision_outbox o "
                            "on t.event_id=o.event_id "
                            "where o.run_id=%s", (ids["run"],)).fetchone()[0]
                        effects = db.execute(
                            "select count(*) from aiops.effect_receipts"
                        ).fetchone()[0]
                        approves = db.execute(
                            "select count(*) from aiops.approval_records "
                            "where decision='APPROVE' and proposal_id=%s",
                            (ids["proposal"],)).fetchone()[0]
                    if has_event_key:
                        self.assertEqual(after["run"]["status"], "RUNNING")
                        self.assertEqual(after["run"]["version"], version + 2)
                        self.assertEqual(len(after["events"]), 2)
                        self.assertEqual(commands, 1)
                    else:
                        self.assertEqual(after["run"], before["run"])
                        self.assertEqual(after["events"], before["events"])
                        self.assertEqual(commands, 0)
                    self.assertEqual((terminal, effects, approves), (0, 0, 0))
                    self._no_effect()

        receipt = {
            "schema": "aiops.worker-core-writer-rollback-gate.v1",
            "source_head": head,
            "environment": "CI_DISPOSABLE_SYNTHETIC_ONLY",
            "core_writer_status": writer_status,
            "migration_event_key_present": bool(has_event_key),
            "core_event_http": event_response.status_code,
            "core_command_http": command_response.status_code,
            "core_unauthorized_event_http": unauthorized.status_code,
            "core_run_status_before": "CREATED",
            "core_run_status_after": after["run"]["status"],
            "core_run_version_delta": after["run"]["version"] - version,
            "core_event_rows_after": len(after["events"]),
            "core_command_receipts_after": commands,
            "core_terminal_014_rows_for_run": terminal,
            "approve_count": approves,
            "effect_receipt_count": effects,
            "execution_allowed": False,
            "effect_allowed": False,
            "sql_dead_injection": False,
            "immutable_012_013_014_mutation": False,
            "temporal_restart": "COVERED_BY_SIBLING_VERTICAL_TEST",
            "oidc_glpi_identity": "NOT_ATTESTED",
            "host_7777_local_operator": "REPORTED_VERIFIED",
            "host_7777_external": "NOT_ATTESTED",
            "universal_exactly_once": "NOT_CLAIMED",
        }
        canonical = json.dumps(
            receipt, sort_keys=True, separators=(",", ":")).encode()
        receipt["payload_sha256"] = hashlib.sha256(canonical).hexdigest()
        target = Path(os.environ["AIOPS_CI_VERTICAL_REJECT_RECEIPT_DIR"])
        self.assertTrue(str(target).startswith("/tmp/hitl-worker-vertical-"))
        target.mkdir(parents=True, exist_ok=True)
        (target / "worker-core-writer-rollback-gate.json").write_text(
            json.dumps(receipt, sort_keys=True, indent=2) + "\n")


if __name__ == "__main__":
    unittest.main()
