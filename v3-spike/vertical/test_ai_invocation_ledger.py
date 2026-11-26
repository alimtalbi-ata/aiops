import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch
from ai_invocation_ledger import InvocationLedger,validate_receipt
from test_dual_model_advisory import provider,change
from test_historical_analyst_critic import HistoricalAnalystCriticTest

class LedgerTest(unittest.TestCase):
    def setUp(self):
        self.root=tempfile.TemporaryDirectory()
        self.addCleanup(self.root.cleanup)
        self.ledger=InvocationLedger(self.root.name)
        self.history=HistoricalAnalystCriticTest().history()
    def execute(self,am=None,cm=None):
        with provider("fixture-a","ANALYST",am) as (a,ar),provider("fixture-c","CRITIC",cm) as (c,cr):
            return self.ledger.execute(self.history,a,c),ar,cr
    def test_completed_and_rejected_persist_after_restart_and_backup(self):
        ok,_,_=self.execute()
        fail,_,cr=self.execute(am=lambda p,r:change(p,r,evidence_ids=["invented"]))
        self.assertEqual(cr,[])
        ids=[ok["review_id"],fail["review_id"]]
        reopened=InvocationLedger(self.root.name)
        good=reopened.read(ids[0])
        self.assertEqual(good["receipt_sha256"],ok["receipt_sha256"])
        self.assertEqual(reopened.read(ids[1])["record"]["invocations"][0]["status"],"REJECTED")
        self.assertNotIn("invented",json.dumps(reopened.read(ids[1])))
        self.assertNotIn("messages",json.dumps(good))
        s=reopened.summary(ids)
        self.assertEqual(s["invocations"],3)
        self.assertEqual(s["groups"][0]["total_tokens"],30)
        with tempfile.TemporaryDirectory() as restored:
            copy=InvocationLedger(restored)
            with closing(reopened.clock.connect()) as src,closing(copy.clock.connect()) as dest:src.backup(dest)
            self.assertEqual(copy.summary(ids),s)
            self.assertEqual(copy.read(ids[0]),good)
    def test_partial_usage_is_not_total(self):
        a,_,_=self.execute()
        b,_,_=self.execute(am=lambda p,r:p.pop("usage"))
        groups=self.ledger.summary([a["review_id"],b["review_id"]])["groups"]
        self.assertEqual(groups[0]["usage_reported_count"],1)
        self.assertIsNone(groups[0]["total_tokens"])
        self.assertEqual(groups[0]["reported_partial_total_tokens"],15)
        self.assertIsNone(groups[0]["cost"])
    def test_tampering_and_missing_id_fail(self):
        a,_,_=self.execute()
        ident=a["review_id"]
        with self.assertRaises(KeyError):self.ledger.read("AI-"+"0"*32)
        with closing(self.ledger.clock.connect()) as db,db:
            db.execute("UPDATE ai_invocation_reviews SET payload_hash=? WHERE review_id=?",("0"*64,ident))
        with self.assertRaises(ValueError):self.ledger.read(ident)
        with self.assertRaises(ValueError):self.ledger.summary([ident])
    def test_capacity_prevents_calls(self):
        with patch("ai_invocation_ledger.MAX_RECORDS",0),patch("ai_invocation_ledger.review") as call:
            with self.assertRaises(ValueError):self.ledger.execute(self.history,{}, {})
            call.assert_not_called()
    def test_invalid_receipts_rejected(self):
        a,_,_=self.execute()
        r=self.ledger.read(a["review_id"])["record"]["invocations"][0]
        for fields in ({"raw_prompt":"secret"},{"cost":1},{"total_tokens":99},{"latency_ms":float("nan")},{"provider_identity_attested":True}):
            with self.assertRaises(ValueError):validate_receipt(dict(r,**fields))

if __name__=="__main__":unittest.main()
