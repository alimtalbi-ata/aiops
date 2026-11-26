import unittest
from hitl_demo import ApprovalGate

class HITLTest(unittest.TestCase):
    def test_bound_one_use(self):
        g=ApprovalGate()
        k=g.request("i","r",["e"])["request_id"]
        self.assertEqual(g.decide(k,"i","r",["e"],True)["decision"],"SIMULATE_ONLY")
        self.assertEqual(g.decide(k,"i","r",["e"],True)["decision"],"DENY")
    def test_changed_context_and_refusal(self):
        for evidence,approved in [(["other"],True),(["e"],False)]:
            g=ApprovalGate()
            k=g.request("i","r",["e"])["request_id"]
            result=g.decide(k,"i","r",evidence,approved)
            self.assertEqual(result["decision"],"DENY")
            self.assertFalse(result["executed_on_host"])


class DurableHITLTest(unittest.TestCase):
    def setUp(self):
        import tempfile
        from pathlib import Path
        from enterprise_clock import EnterpriseClock
        from hitl_demo import DurableApprovalGate
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve()
        self.clock=EnterpriseClock(self.root)
        self.gate=DurableApprovalGate(self.clock)
        self.incident="INC-CI-INGEST-"+"a"*32
        self.run="RUN-"+"A"*16
        self.refs=[{"evidence_id":"EVD-A","payload_hash":"a"*64},
                   {"evidence_id":"EVD-B","payload_hash":"b"*64}]

    def request(self):
        return self.gate.request(self.incident,self.run,self.refs)["request_id"]

    def decide(self,key,refs=None,approved=True):
        return self.gate.decide(key,self.incident,self.run,self.refs if refs is None else refs,approved)

    def test_receipt_reopen_and_backup(self):
        from contextlib import closing
        from enterprise_clock import EnterpriseClock
        from hitl_demo import DurableApprovalGate
        key=self.request()
        result=self.decide(key,list(reversed(self.refs)))
        self.assertEqual(result["decision"],"SIMULATE_ONLY")
        persisted=self.gate.read_receipt(result["receipt_id"])
        self.assertEqual(persisted["receipt_sha256"],result["receipt_sha256"])
        self.assertNotIn(key,str(persisted))
        self.assertFalse(persisted["record"]["production_authorized"])
        self.assertEqual(self.decide(key)["decision"],"DENY")
        pending=self.request()
        self.gate=DurableApprovalGate(EnterpriseClock(self.root))
        self.assertEqual(self.decide(pending)["decision"],"DENY")
        self.assertEqual(self.gate.read_receipt(result["receipt_id"]),persisted)
        other=self.root/"restore"
        other.mkdir(mode=0o700)
        restored=EnterpriseClock(other)
        with closing(self.clock.connect()) as src, closing(restored.connect()) as dst:
            src.backup(dst)
        self.assertEqual(DurableApprovalGate(restored).read_receipt(result["receipt_id"]),persisted)

    def test_invalid_context_denial_and_tamper(self):
        from contextlib import closing
        key=self.request()
        result=self.decide(key,[dict(self.refs[0],payload_hash="c"*64),self.refs[1]])
        self.assertEqual(result["decision"],"DENY")
        self.assertEqual(self.decide(key)["decision"],"DENY")
        self.assertEqual(self.gate.read_receipt(result["receipt_id"])["record"]["decision"],"DENY")
        with closing(self.clock.connect()) as db,db:
            db.execute("UPDATE hitl_decision_receipts SET payload_hash=? WHERE receipt_id=?",("0"*64,result["receipt_id"]))
        with self.assertRaises(ValueError):
            self.gate.read_receipt(result["receipt_id"])

    def test_concurrent_replay_and_refusal(self):
        from concurrent.futures import ThreadPoolExecutor
        key=self.request()
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes=list(pool.map(self.decide,[key,key]))
        self.assertEqual(sorted(x["decision"] for x in outcomes),["DENY","SIMULATE_ONLY"])
        self.assertEqual(self.decide(self.request(),approved=False)["decision"],"DENY")

    def test_storage_failure_does_not_return_simulation(self):
        from contextlib import closing
        key=self.request()
        with closing(self.clock.connect()) as db,db:
            db.execute("DROP TABLE hitl_decision_receipts")
        import sqlite3
        with self.assertRaises(sqlite3.Error):
            self.decide(key)
        self.assertEqual(self.decide(key)["decision"],"DENY")

    def test_read_only_init_never_opens_storage_and_request_fails_closed(self):
        from unittest.mock import Mock
        from hitl_demo import DurableApprovalGate
        clock=Mock()
        clock.connect.side_effect=OSError("storage unavailable")
        gate=DurableApprovalGate(clock)
        clock.connect.assert_not_called()
        with self.assertRaises(OSError):
            gate.request(self.incident,self.run,self.refs)
        self.assertEqual(gate.pending,{})
        clock.connect.assert_called_once_with()


    def test_action_reservation_binding_replay_and_conflict(self):
        from unittest.mock import patch
        from hitl_demo import DurableApprovalGate
        scope={"action":"RESET_LAB_HTTP_DELAY","resource":"NODE-CI-ROOT","target_id":"c"*32}
        policy={"policy_decision":"SIMULATE","simulation_only":True,"operational_decision":"DENY",
                "executed_on_host":False,"production_authorized":False}
        def approval(action):
            key=self.gate.request(self.incident,self.run,self.refs,lab_action=action)["request_id"]
            return self.gate.decide(key,self.incident,self.run,self.refs,True,lab_action=action)
        def reserve(result,action=scope,refs=None,workflow=None):
            return self.gate.reserve_lab_action(result["receipt_id"],result["receipt_sha256"],self.incident,
                       self.run,self.refs if refs is None else refs,action,self.run if workflow is None else workflow,18001)
        generic=approval(None)
        result=approval(scope)
        with patch("policy_demo.simulation_decision",return_value=policy):
            for invalid in (lambda:reserve(generic),lambda:reserve(result,dict(scope,target_id="d"*32)),
                            lambda:reserve(result,refs=[dict(self.refs[0],payload_hash="d"*64),self.refs[1]]),
                            lambda:reserve(result,workflow="RUN-"+"B"*16)):
                with self.assertRaises(ValueError):invalid()
            first=reserve(result)
            self.assertEqual(first["disposition"],"RESERVED_NO_EXECUTION")
            self.assertFalse(first["action_authorized"])
            self.gate=DurableApprovalGate(self.clock)
            second=reserve(result)
            self.assertEqual(second["disposition"],"ALREADY_RESERVED_BLOCKED")
            self.assertEqual(first["reservation_sha256"],second["reservation_sha256"])
            with self.assertRaises(ValueError):reserve(approval(scope))

    def test_action_reservation_expiry_and_policy(self):
        from unittest.mock import patch
        from contextlib import closing
        import json
        scope={"action":"RESET_LAB_HTTP_DELAY","resource":"NODE-CI-ROOT","target_id":"e"*32}
        key=self.gate.request(self.incident,self.run,self.refs,lab_action=scope)["request_id"]
        wrong=self.gate.decide(key,self.incident,self.run,self.refs,True,lab_action=dict(scope,target_id="f"*32))
        self.assertEqual(wrong["decision"],"DENY")
        key=self.gate.request(self.incident,self.run,self.refs,lab_action=scope)["request_id"]
        result=self.gate.decide(key,self.incident,self.run,self.refs,True,lab_action=scope)
        def reserve(digest):
            return self.gate.reserve_lab_action(result["receipt_id"],digest,self.incident,self.run,
                                               self.refs,scope,self.run,18001)
        with patch("policy_demo.simulation_decision",return_value={"policy_decision":"DENY"}):
            with self.assertRaises(ValueError):reserve(result["receipt_sha256"])
        record=self.gate.read_receipt(result["receipt_id"])["record"]
        record["recorded_at"]="2000-01-01T00:00:00+00:00"
        digest=self.gate._hash(record)
        with closing(self.clock.connect()) as db,db:
            db.execute("UPDATE hitl_decision_receipts SET payload=?,payload_hash=? WHERE receipt_id=?",
                       (json.dumps(record),digest,result["receipt_id"]))
        with patch("policy_demo.simulation_decision",return_value={"policy_decision":"SIMULATE","simulation_only":True,
                   "operational_decision":"DENY","executed_on_host":False,"production_authorized":False}):
            with self.assertRaises(ValueError):reserve(digest)


    def _fence_fixture(self):
        from lab_target_fence import LabTargetFence
        binding = dict(run_id=self.run, incident_id=self.incident,
                       resource="NODE-CI-ROOT",
                       context_sha256=self.gate.binding(self.incident,self.run,self.refs))
        fence = LabTargetFence(**binding)
        scope = fence.scope()
        key = self.gate.request(self.incident,self.run,self.refs,lab_action=scope)["request_id"]
        approval = self.gate.decide(key,self.incident,self.run,self.refs,True,lab_action=scope)
        def reserve(gate):
            return gate.reserve_lab_action(approval["receipt_id"],approval["receipt_sha256"],
                self.incident,self.run,self.refs,scope,self.run,18001)
        policy = {"policy_decision":"SIMULATE","simulation_only":True,
                  "operational_decision":"DENY","executed_on_host":False,
                  "production_authorized":False}
        return fence,binding,reserve,policy

    def test_target_fence_rejects_replay_after_preclaim_snapshot_restore(self):
        from contextlib import closing
        from unittest.mock import patch
        from enterprise_clock import EnterpriseClock
        from hitl_demo import DurableApprovalGate
        from lab_target_fence import LabTargetFence
        fence,binding,reserve,policy = self._fence_fixture()
        other = self.root/"preclaim-snapshot"
        other.mkdir(mode=0o700)
        restored = EnterpriseClock(other)
        with closing(self.clock.connect()) as src, closing(restored.connect()) as dst:
            src.backup(dst)
        with patch("policy_demo.simulation_decision",return_value=policy):
            first = reserve(self.gate)
            self.assertEqual(fence.claim(first)["status"],"CLAIMED_NO_EXECUTION")
            # An old snapshot has no reservation: SQLite alone admits it again.
            replay = reserve(DurableApprovalGate(restored))
        self.assertEqual(replay["disposition"],"RESERVED_NO_EXECUTION")
        self.assertEqual(replay["reservation_sha256"],first["reservation_sha256"])
        blocked = fence.claim(replay)
        self.assertEqual(blocked["status"],"UNKNOWN_BLOCKED")
        self.assertFalse(blocked["action_authorized"])
        self.assertFalse(blocked["production_authorized"])
        restarted = LabTargetFence(**binding)
        self.assertNotEqual(restarted.scope()["target_id"],fence.scope()["target_id"])
        with self.assertRaises(ValueError):
            restarted.claim(replay)

    def test_target_fence_concurrent_claim_and_tamper(self):
        from concurrent.futures import ThreadPoolExecutor
        from unittest.mock import patch
        from copy import deepcopy
        fence,_,reserve,policy = self._fence_fixture()
        with patch("policy_demo.simulation_decision",return_value=policy):
            reservation = reserve(self.gate)
        wrong = deepcopy(reservation)
        wrong["binding"]["workflow_id"] = "RUN-"+"B"*16
        unsigned = {k:v for k,v in wrong.items() if k not in ("reservation_sha256","disposition")}
        wrong["reservation_sha256"] = self.gate._hash(unsigned)
        with self.assertRaises(ValueError):
            fence.claim(wrong)
        with self.assertRaises(ValueError):
            fence.claim(dict(reservation,reservation_sha256="0"*64))
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(fence.claim,[reservation,reservation]))
        self.assertEqual(sorted(x["status"] for x in outcomes),["CLAIMED_NO_EXECUTION","UNKNOWN_BLOCKED"])
        self.assertTrue(all(x["action_authorized"] is False and x["executed_on_host"] is False
                            for x in outcomes))

    def test_target_fence_existing_reservation_is_ambiguous_even_on_first_contact(self):
        from unittest.mock import patch
        fence,_,reserve,policy = self._fence_fixture()
        with patch("policy_demo.simulation_decision",return_value=policy):
            first = reserve(self.gate)
            replay = reserve(self.gate)
        self.assertEqual(fence.claim(replay)["status"],"UNKNOWN_BLOCKED")
        self.assertEqual(fence.claim(first)["status"],"UNKNOWN_BLOCKED")


    def test_e17_target_real_http_one_shot_recovery(self):
        import runpy
        import threading
        from pathlib import Path
        from statistics import median
        from unittest.mock import patch
        fixture=runpy.run_path(str(Path(__file__).resolve().parents[1]/"kit"/"poc-multiasset-observed.py"))
        policy={"policy_decision":"SIMULATE","simulation_only":True,"operational_decision":"DENY",
                "executed_on_host":False,"production_authorized":False}
        with fixture["LabRecoveryTarget"]() as app:
            thread=threading.Thread(target=app.serve_forever,daemon=True)
            thread.start()
            try:
                baseline=median(fixture["measure"](app))
                app.inject_fault()
                incident=median(fixture["measure"](app))
                scope=app.bind(self.gate,self.incident,self.run,self.refs)
                key=self.gate.request(self.incident,self.run,self.refs,lab_action=scope)["request_id"]
                approval=self.gate.decide(key,self.incident,self.run,self.refs,True,lab_action=scope)
                with patch("policy_demo.simulation_decision",return_value={"policy_decision":"DENY"}):
                    with self.assertRaises(ValueError):
                        app.simulate(approval["receipt_id"],approval["receipt_sha256"],18001)
                self.assertEqual(app.delay,fixture["CONFIGS"][0][-1])
                with patch("policy_demo.simulation_decision",return_value=policy):
                    result=app.simulate(approval["receipt_id"],approval["receipt_sha256"],18001)
                    self.assertEqual(result["status"],"SIMULATED")
                    self.assertEqual(result["binding"]["lab_action"],scope)
                    self.assertFalse(result["executed_on_host"])
                    self.assertFalse(result["production_authorized"])
                    self.assertEqual(app.simulate(approval["receipt_id"],approval["receipt_sha256"],18001)["status"],"UNKNOWN_BLOCKED")
                recovery=median(fixture["measure"](app))
                self.assertGreater(incident,2*baseline)
                self.assertLess(recovery,incident/2)
                self.assertEqual(len(app.records),15)
                self.assertEqual(app.read_action_result(result["receipt_id"]),result)
                result["binding"]["run_id"]="tampered"
                self.assertEqual(app.read_action_result(result["receipt_id"])["binding"]["run_id"],self.run)
                with self.assertRaises(ValueError):
                    app.bind(self.gate,self.incident,self.run,self.refs)
            finally:
                app.shutdown()
                thread.join(5)
