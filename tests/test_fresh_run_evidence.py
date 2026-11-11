import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
import unittest
from shared.evidence_identity import canonical_evidence,evidence_digest
from app.shared.fresh_run_evidence import verify_run_evidence

RID="RUN-QUALIFICATION-123456"
def fixture():
    row={"evidence_id":"EVD-1","source":"synthetic","external_id":"E-1",
         "observed_at":None,"claim":"synthetic stage completed","confidence":1.0,
         "provenance":{"run_id":RID,"synthetic":True,"identity_contract":"canonical-envelope-v1"},
         "payload":{"stage":"NORMALIZE"}}
    row["payload_hash"]=evidence_digest(canonical_evidence(**{k:row[k] for k in (
        "source","external_id","observed_at","claim","confidence","provenance","payload")}))
    return row
def verify(row=None,listing=None,events=None):
    row=fixture() if row is None else row
    listing={"run_id":RID,"items":[{"evidence_id":"EVD-1","payload_hash":row["payload_hash"]}],
             "payload_excluded":True} if listing is None else listing
    events=[{"evidence_ids":["EVD-1"]}] if events is None else events
    return verify_run_evidence(RID,events,listing,lambda _:row)

class FakeCursor:
    def __init__(self,rows):self.rows=rows;self.queries=[]
    def __enter__(self):return self
    def __exit__(self,*args):return False
    def execute(self,query,params=None):self.queries.append((query,params))
    def fetchall(self):return self.rows
class FakeConnection:
    def __init__(self,rows):self.fake=FakeCursor(rows)
    def cursor(self):return self.fake

class EvidenceReadbackTests(unittest.TestCase):
    def test_direct_sql_readonly_links(self):
        rows=[("EVD-1","a"*64,RID,True)]
        conn=FakeConnection(rows)
        result=verify_evidence_sql(RID,{"EVD-1"},conn)
        self.assertEqual(result["database_direct_sql"],"PASS")
        self.assertEqual(conn.fake.queries[0][0],"SET TRANSACTION READ ONLY")
        self.assertEqual(conn.fake.queries[1][1],(RID,["EVD-1"]))
    def test_direct_sql_missing_row_fails(self):
        with self.assertRaisesRegex(ValueError,"SQL_EVIDENCE_ROWS_MISSING"):
            verify_evidence_sql(RID,{"EVD-1"},FakeConnection([]))
    def test_direct_sql_wrong_run_link_fails(self):
        with self.assertRaisesRegex(ValueError,"SQL_RUN_EVENT_LINK_MISMATCH"):
            verify_evidence_sql(RID,{"EVD-1"},FakeConnection([("EVD-1","a"*64,RID,False)]))
    def test_direct_sql_invalid_digest_fails(self):
        with self.assertRaisesRegex(ValueError,"SQL_EVIDENCE_DIGEST_INVALID"):
            verify_evidence_sql(RID,{"EVD-1"},FakeConnection([("EVD-1","bad",RID,True)]))

    def test_verified_digest_but_not_signature_or_direct_sql(self):
        result=verify()
        self.assertEqual(result["canonical_sha256_readback"],"PASS")
        self.assertEqual(result["verified_persisted_evidence"],1)
        self.assertEqual(result["cryptographic_signature"],"NOT_VERIFIED")
        self.assertEqual(result["database_direct_sql"],"NOT_VERIFIED")
    def test_digest_tampering_rejected(self):
        row=fixture();row["payload"]["stage"]="TAMPERED"
        with self.assertRaisesRegex(ValueError,"EVIDENCE_DIGEST_MISMATCH"):verify(row)
    def test_cross_run_provenance_rejected(self):
        row=fixture();row["provenance"]["run_id"]="RUN-OTHER"
        with self.assertRaisesRegex(ValueError,"EVIDENCE_PROVENANCE_RUN_MISMATCH"):verify(row)
    def test_missing_stage_link_rejected(self):
        with self.assertRaisesRegex(ValueError,"STAGE_EVIDENCE_LINK_MISSING"):verify(events=[{"evidence_ids":[]}])
    def test_missing_core_readback_rejected(self):
        with self.assertRaisesRegex(ValueError,"CORE_EVIDENCE_READBACK_INCOMPLETE"):
            verify(listing={"run_id":RID,"items":[],"payload_excluded":True})
    def test_unverified_synthetic_provenance_rejected(self):
        row=fixture();row["provenance"]["synthetic"]=False
        with self.assertRaisesRegex(ValueError,"EVIDENCE_NOT_SYNTHETIC"):verify(row)
if __name__=="__main__":unittest.main()
