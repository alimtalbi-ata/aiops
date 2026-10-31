"""CI-only Core outbox -> Worker -> real Temporal signal/ACK test.

Only a synthetic REJECT fixture and a no-effect Temporal notification sink are
used. No identity attestation, human approval, LIVE, or executor.
"""
import asyncio
import hashlib
import json
import os
import uuid
from urllib.parse import urlsplit

import psycopg
from temporalio import workflow
from temporalio.client import Client
from temporalio.worker import Worker


@workflow.defn(name="CIHITLNoEffectNotificationSink", sandboxed=False)
class NotificationSink:
    def __init__(self):
        self.decisions = []

    @workflow.signal(name="submit_hitl_decision")
    def observe(self, decision: dict) -> None:
        self.decisions.append(dict(decision))

    @workflow.run
    async def run(self) -> dict:
        await workflow.wait_condition(lambda: len(self.decisions) >= 2, timeout=90)
        return {"decisions": self.decisions, "execution_allowed": False,
                "effect_allowed": False}


def require_disposable():
    if (os.getenv("AIOPS_CI_DISPOSABLE") != "YES"
            or os.getenv("GITHUB_ACTIONS") != "true"
            or os.getenv("COMPOSE_PROFILES") != "test"):
        raise RuntimeError("refuse_non_disposable_runtime")
    dsn = os.environ["DATABASE_URL"]
    parsed = urlsplit(dsn)
    if parsed.hostname != "aiops2-postgres" or parsed.path != "/aiops":
        raise RuntimeError("refuse_non_ci_database")
    return dsn


def seed(dsn, run_id, suffix):
    analysis, critique = "CI-HITL-AN-" + suffix, "CI-HITL-CR-" + suffix
    proposal, approval, event = ("CI-HITL-ACT-" + suffix,
                                 "CI-HITL-APR-" + suffix, "CI-HITL-HDO-" + suffix)
    evidence = "CI-HITL-EVD-" + suffix
    digest = hashlib.sha256(("SYNTHETIC_UNVERIFIED:" + suffix).encode()).hexdigest()
    evidence_ids = json.dumps([evidence])
    action = {"action_id": "CI-FIXTURE", "risk_tier": "LOW",
              "target_ci_id": "CI-SYNTHETIC", "advisory_only": True,
              "requires_human_approval": True}
    with psycopg.connect(dsn, connect_timeout=5) as c:
        c.execute("insert into aiops.runs(run_id,mode,scenario_id,status,idempotency_key) "
                  "values(%s,'DEMO','CI-HITL','CREATED',%s)",
                  (run_id, "ci-run-" + suffix))
        c.execute("insert into aiops.evidence "
                  "(evidence_id,source,claim,confidence,provenance,payload_hash,payload) "
                  "values(%s,'ci-fixture','synthetic notification only',0.5,"
                  "'{\"synthetic\":true}',%s,'{}')", (evidence, digest))
        c.execute("insert into aiops.analysis_records "
                  "(analysis_id,run_id,idempotency_key,revision,contract_version,provider,"
                  "model,prompt_version,evidence_ids,evidence_set_hash,output,confidence,status) "
                  "values(%s,%s,%s,1,'ci','ci-fixture','none','ci',%s,%s,%s,0.5,'VALID')",
                  (analysis, run_id, "ci-analysis-" + suffix, evidence_ids, digest,
                   json.dumps({"recommended_actions": [action]})))
        c.execute("insert into aiops.critique_records "
                  "(critique_id,idempotency_key,analysis_id,run_id,contract_version,"
                  "provider,model,validated,evidence_ids,output,diagnostic_confidence) "
                  "values(%s,%s,%s,%s,'ci','ci-fixture','none',true,%s,%s,0.5)",
                  (critique, "ci-critique-" + suffix, analysis, run_id, evidence_ids,
                   json.dumps({"issues": [], "unsafe_actions": []})))
        c.execute("insert into aiops.action_proposals "
                  "(proposal_id,run_id,analysis_id,critique_id,source_action_id,"
                  "proposal_revision,target_ci_id,action_type,risk_tier,evidence_ids,"
                  "preconditions,expected_postconditions,proposal_hash,status,expires_at) "
                  "values(%s,%s,%s,%s,'CI-FIXTURE',1,'CI-SYNTHETIC',"
                  "'COLLECT_DIAGNOSTICS','LOW',%s,'[\"ci precondition\"]',"
                  "'[\"ci postcondition\"]',%s,'PROPOSED',now()+interval '1 hour')",
                  (proposal, run_id, analysis, critique, evidence_ids, digest))
        c.execute("insert into aiops.approval_records "
                  "(approval_id,proposal_id,proposal_hash,actor_id,actor_role,decision,"
                  "nonce,expires_at,audit) values(%s,%s,%s,'SYNTHETIC_UNVERIFIED',"
                  "'ci_fixture','REJECT',%s,now()+interval '1 hour',%s)",
                  (approval, proposal, digest, "ci-nonce-" + suffix,
                   json.dumps({"synthetic": True, "identity_attested": False})))
        c.execute("update aiops.action_proposals set status='REJECTED' "
                  "where proposal_id=%s", (proposal,))
        c.execute("insert into aiops.hitl_decision_outbox "
                  "(event_id,proposal_id,run_id,proposal_hash,proposal_revision,"
                  "decision,source_status,approval_id) "
                  "values(%s,%s,%s,%s,1,'REJECT','REJECTED',%s)",
                  (event, proposal, run_id, digest, approval))
    return event, proposal, digest


def read_state(dsn, event, proposal):
    with psycopg.connect(dsn, connect_timeout=5) as c:
        row = c.execute("select status,attempts,lease_token from "
                        "aiops.hitl_decision_outbox where event_id=%s", (event,)).fetchone()
        effects = c.execute("select count(*) from aiops.effect_receipts "
                            "where proposal_id=%s", (proposal,)).fetchone()[0]
    if effects != 0:
        raise AssertionError("synthetic_effect_receipt_forbidden")
    return row


async def wait_delivered(dsn, event, proposal, attempts):
    for _ in range(75):
        row = await asyncio.to_thread(read_state, dsn, event, proposal)
        if row[0] == "DELIVERED" and row[1] == attempts:
            return row
        await asyncio.sleep(1)
    raise AssertionError(f"outbox_delivery_not_observed_attempt_{attempts}")


async def main():
    dsn = require_disposable()
    suffix = uuid.uuid4().hex
    run_id = "CI-HITL-RUN-" + suffix
    client = await Client.connect("aiops2-temporal:7233")
    async with Worker(client, task_queue="ci-hitl-notification-sink",
                      workflows=[NotificationSink]):
        handle = await client.start_workflow(NotificationSink.run, id=run_id,
                                             task_queue="ci-hitl-notification-sink")
        event, proposal, digest = await asyncio.to_thread(seed, dsn, run_id, suffix)
        first = await wait_delivered(dsn, event, proposal, 1)
        # Exit while the CI sink workflow still waits for its second signal.
        # A fresh sink Worker must replay persisted Temporal history to finish.
        # This is NOT a production Worker or Temporal server restart.
    # Synthetic duplicate delivery: re-queue this CI fixture only. This is
    # NOT proof of an actual network ACK loss or a real human identity.
    with psycopg.connect(dsn, connect_timeout=5) as c:
        c.execute("update aiops.hitl_decision_outbox set status='PENDING',"
                  "available_at=now(),lease_owner=null,lease_token=null,"
                  "lease_until=null,delivered_at=null where event_id=%s "
                  "and status='DELIVERED' and attempts=1", (event,))
        if c.execute("select status from aiops.hitl_decision_outbox "
                     "where event_id=%s", (event,)).fetchone()[0] != "PENDING":
            raise AssertionError("ci_replay_not_queued")
    async with Worker(client, task_queue="ci-hitl-notification-sink",
                      workflows=[NotificationSink]):
        result = await asyncio.wait_for(handle.result(), timeout=100)
        second = await wait_delivered(dsn, event, proposal, 2)
    expected = {"proposal_id": proposal, "proposal_hash": digest,
                "proposal_revision": 1, "decision": "REJECT", "source_status": "REJECTED"}
    if result["decisions"] != [expected, expected]:
        raise AssertionError("temporal_duplicate_signal_binding_mismatch")
    if result["execution_allowed"] is not False or result["effect_allowed"] is not False:
        raise AssertionError("signal_sink_effect_fence_invalid")
    if first[2] == second[2] or len(str(second[2])) != 64:
        raise AssertionError("lease_token_not_rotated_and_hashed")
    print(json.dumps({"result": "PASS", "mode": "DEMO",
                      "scope": "Core outbox API -> Worker -> Temporal CI sink -> Core ACK",
                      "production_incident_workflow": "NOT_TESTED",
                      "identity": "NOT_ATTESTED", "human_approval": "NOT_TESTED",
                      "run_id": run_id, "outbox_event": event,
                      "outbox_state": second[0], "attempts": second[1],
                      "temporal_signals": len(result["decisions"]),
                      "replay": "CI_SYNTHETIC_REQUEUE_NOT_REAL_LOST_ACK",
                      "ci_sink_worker_restart_inflight": "OBSERVED",
                      "production_worker_restart_inflight": "NOT_TESTED",
                      "temporal_server_restart_inflight": "NOT_TESTED",
                      "effect_receipts": 0, "execution_allowed": False,
                      "effect_allowed": False}, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
