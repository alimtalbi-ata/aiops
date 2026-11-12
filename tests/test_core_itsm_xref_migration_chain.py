"""PG16 disposable-only ordered migration qualification; pinned historical source fixtures.

The 009/010/011 fixtures are byte-identical Git blobs from #194 at
40d38705cf2bde3be6052340442c117a81908f65. They are NOT installed
migrations in this PR. Architect must requalify against final integrated SHAs.
"""
import hashlib
import os
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
import unittest
import psycopg

ROOT=Path(__file__).resolve().parent.parent
SOURCE=ROOT/"tests"/"fixtures"/"core_xref_chain"
MIG=ROOT/"db"/"migrations"
PINNED={
    "009_ai_decision_ledger.sql":"bfed91982654b6baf0026408fa5134a22af421bb",
    "010_evidence_identity.sql":"1ddafd94639af60ce38b6df0acafd7f63d6b4af2",
    "011_hitl_decision_outbox.sql":"b096af57cb19b9618e3d7d4d68a8ef3d56890934",
}

@unittest.skipUnless(os.getenv("AIOPS_XREF_CI_DISPOSABLE")=="1","disposable CI only")
class CombinedXrefMigrationChain(unittest.TestCase):
    def test_pg16_order_idempotence_and_transaction_rollback(self):
        url=os.environ["DATABASE_URL"]
        parsed=urlsplit(url)
        if parsed.hostname!="127.0.0.1" or parsed.port!=5432 or parsed.path!="/aiops":
            raise RuntimeError("Refusing non-disposable PostgreSQL target")
        self.assertFalse((MIG/"009_itsm_xref_read.sql").exists(),
                         "Never import the conflicting historical xref 009")
        scripts=[]
        for name in ("001_schema.sql","004_operational_model.sql",
                     "009_ai_decision_ledger.sql","010_evidence_identity.sql",
                     "011_hitl_decision_outbox.sql","012_itsm_xref_read.sql"):
            path=(SOURCE if name in PINNED else MIG)/name
            content=path.read_bytes()
            if name in PINNED:
                blob=hashlib.sha1(b"blob "+str(len(content)).encode()+b"\0"+content).hexdigest()
                self.assertEqual(blob,PINNED[name],name+" fixture changed")
            scripts.append((name,content.decode("utf-8")))
        dbname="aiops_xref_chain_ci"
        chainurl=urlunsplit((parsed.scheme,parsed.netloc,"/"+dbname,parsed.query,parsed.fragment))
        with psycopg.connect(url,autocommit=True) as admin:
            # No DROP before CREATE: unexpected existing database is a hard failure.
            admin.execute("create database "+dbname)
        try:
            with psycopg.connect(chainurl) as c:
                for name,sql in scripts:
                    with self.subTest(stage="rollback_trial",migration=name):
                        c.execute(sql)
                self.assertIsNotNone(c.execute(
                    "select to_regclass('aiops.itsm_xref_events')").fetchone()[0])
                c.rollback()  # PostgreSQL DDL rollback, no persistent side effects.
            with psycopg.connect(chainurl) as c:
                self.assertIsNone(c.execute(
                    "select to_regclass('aiops.itsm_xref_events')").fetchone()[0])
                self.assertIsNone(c.execute(
                    "select to_regclass('aiops.hitl_decision_outbox')").fetchone()[0])
            for iteration in (1,2):
                with psycopg.connect(chainurl) as c:
                    for name,sql in scripts:
                        with self.subTest(stage="idempotence",iteration=iteration,migration=name):
                            c.execute(sql)
            with psycopg.connect(chainurl) as c:
                for table in ("analysis_records","hitl_decision_outbox",
                              "itsm_xref_events","tenant_resource_ownership"):
                    self.assertIsNotNone(c.execute(
                        "select to_regclass(%s)",("aiops."+table,)).fetchone()[0])
        finally:
            with psycopg.connect(url,autocommit=True) as admin:
                admin.execute("drop database "+dbname+" with (force)")

if __name__=="__main__":
    unittest.main()
