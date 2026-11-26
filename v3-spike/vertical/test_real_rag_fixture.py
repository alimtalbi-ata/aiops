import tempfile,unittest
from ai_invocation_ledger import InvocationLedger
from poc_real_rag import seed,qualify
from test_rag_model_advisory import provider
from enterprise_context import digest

class RealRagFixtureTest(unittest.TestCase):
    def test_persistent_campaign_and_receipts(self):
        with tempfile.TemporaryDirectory() as root:
            ledger=InvocationLedger(root)
            history,context=seed(ledger)
            self.assertEqual(history["verified_evidence_count"],8)
            self.assertTrue(context["candidates"][0]["reference_context"])
            with provider("fixture-a","ANALYST") as (a,ar),provider("fixture-c","CRITIC") as (c,cr):
                r=ledger.execute_rag(history,a,c)
            out=r["assessment"]
            self.assertTrue(qualify(out,context)["pass"])
            restored=InvocationLedger(root)
            rec=restored.read(r["review_id"])
            self.assertEqual(rec["record"]["context_sha256"],digest(context))
            self.assertEqual(rec["record"]["invocations"],out["invocations"])
            self.assertEqual(restored.summary([r["review_id"]])["invocations"],2)
            self.assertNotIn("excerpt",str(rec))
    def test_rejected_receipt_persisted_and_quality_fails(self):
        with tempfile.TemporaryDirectory() as root:
            ledger=InvocationLedger(root)
            history,context=seed(ledger)
            with provider("fixture-a","ANALYST",lambda o:o.update(reference_ids=["invented"])) as (a,ar),provider("fixture-c","CRITIC") as (c,cr):
                r=ledger.execute_rag(history,a,c)
            self.assertEqual(cr,[])
            self.assertFalse(qualify(r["assessment"],context)["pass"])
            self.assertEqual(ledger.read(r["review_id"])["record"]["invocations"][0]["status"],"REJECTED")

if __name__=="__main__":unittest.main()
