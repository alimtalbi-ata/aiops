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
                    started = post(route + "/command", {
                        "expected_version": run["version"],
                        "idempotency_key": "CI-VERTICAL-START-" + ids["run"],
                        "command": "START"})
                    version = started["version"]
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
                    for stage, event_type, binding, status, decision, extra in stages:
                        body = {
                            "expected_version": version,
                            "stage": stage, "event_type": event_type,
                            "event_key": "CI-VERTICAL-" + stage,
                            "status": status, "decision": decision,
                            "evidence_ids": [ids["evidence"]],
                            "payload": {
                                binding: ids[binding],
                                "tenant_id": base.TENANT,
                                "run_id": ids["run"],
                                "synthetic": True,
                                "execution_allowed": False,
                                "effect_allowed": False, **extra},
                        }
                        event = post(route + "/events", body)
                        self.assertIs(event["idempotent"], False)
                        version = event["version"]
                        if stage == "VERIFY":
                            # Core event-key replay is idempotent only when
                            # the caller uses the current canonical version.
                            body["expected_version"] = version
                            repeated = post(route + "/events", body)
                            self.assertIs(repeated["idempotent"], True)
                            self.assertEqual(repeated["version"], version)
                    post(route + "/gates", {
                        "stage": "POLICY", "state": "PASS",
                        "decision": "SIMULATE",
                        "reason": "synthetic advisory; HITL REJECT veto",
                        "evidence_ids": [ids["evidence"]],
                        "required_evidence": ["analyst", "critic"]})
                    blocked = post(route + "/command", {
                        "expected_version": version,
                        "idempotency_key": "CI-VERTICAL-BLOCK-" + ids["run"],
                        "command": "BLOCK"})
                    self.assertEqual(blocked["status"], "BLOCKED")
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
                    "core_run_api": "OBSERVED_CI_DISPOSABLE_ASGI",
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


if __name__ == "__main__":
    unittest.main()
