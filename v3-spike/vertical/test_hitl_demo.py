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
