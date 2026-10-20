"""API-level identity and idempotency tests; no server or database required."""
import importlib.util
import os
import pathlib
import sys
import unittest
from contextlib import contextmanager
from unittest.mock import patch

from fastapi import HTTPException

ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"app"))
os.environ.setdefault("AIOPS_INTERNAL_TOKEN","unit-only-token")
os.environ.setdefault("DATABASE_URL","postgresql://fixture:fixture@localhost/fixture")
spec=importlib.util.spec_from_file_location("aiops_evidence_ingest",ROOT/"app"/"evidence"/"main.py")
API=importlib.util.module_from_spec(spec)
spec.loader.exec_module(API)
from shared.evidence_identity import canonical_evidence,evidence_digest


def event(**overrides):
    data=dict(
        source="san-monitor",external_id="RUN-1:path-1",
        observed_at="2026-10-20T08:00:00+02:00",
        claim="Synthetic SAN multipath degraded",confidence=0.9,
        provenance={"synthetic":True,"run_id":"RUN-1"},
        payload={"node_id":"ACME-SAN-FABRIC-A","active_paths":1}
    )
    data.update(overrides)
    return API.In(**data)


class FakeCursor:
    def __init__(self,row):self.row=row
    def fetchone(self):return self.row


class FakeConnection:
    def __init__(self,inserted,previous=None):
        self.inserted=inserted
        self.previous=previous
        self.calls=[]
    def execute(self,sql,args):
        self.calls.append((sql,args))
        if sql.startswith("insert into aiops.evidence"):
            return FakeCursor(self.inserted)
        if sql.startswith("select evidence_id,payload_hash"):
            return FakeCursor(self.previous)
        raise AssertionError("Unexpected SQL:"+sql)


@contextmanager
def connection(value):
    yield value


class EvidenceIngestionTests(unittest.TestCase):
    def setUp(self):API.INTERNAL_TOKEN="unit-only-token"
    def test_first_insert_uses_unique_index_and_full_envelope(self):
        conn=FakeConnection(("EVD-NEW",))
        with patch.object(API,"db",lambda:connection(conn)):
            value=API.create(event(),authorization="Bearer unit-only-token")
        self.assertFalse(value["deduplicated"])
        self.assertEqual(value["evidence_id"],"EVD-NEW")
        self.assertIn("on conflict do nothing",conn.calls[0][0])
        self.assertEqual(conn.calls[0][1][4],"Synthetic SAN multipath degraded")
        self.assertEqual(conn.calls[0][1][3],"2026-10-20T06:00:00.000000Z")

    def test_exact_replay_returns_existing_evidence(self):
        payload=event()
        body=payload.model_dump()
        body["provenance"]={**body["provenance"],"identity_contract":"canonical-envelope-v1"}
        digest=evidence_digest(canonical_evidence(**body))
        conn=FakeConnection(None,("EVD-PRIOR",digest))
        with patch.object(API,"db",lambda:connection(conn)):
            value=API.create(payload,authorization="Bearer unit-only-token")
        self.assertTrue(value["deduplicated"])
        self.assertEqual(value["evidence_id"],"EVD-PRIOR")
        self.assertIn("external_id=%s",conn.calls[1][0])

    def test_reused_external_id_with_changed_observation_is_conflict(self):
        conn=FakeConnection(None,("EVD-PRIOR","other-observation-hash"))
        with patch.object(API,"db",lambda:connection(conn)):
            with self.assertRaises(HTTPException) as result:
                API.create(event(claim="Changed observation"),authorization="Bearer unit-only-token")
        self.assertEqual(result.exception.status_code,409)
        self.assertEqual(result.exception.detail["code"],"evidence_identity_conflict")

    def test_no_external_id_falls_back_to_full_digest(self):
        payload=event(external_id=None)
        body=payload.model_dump()
        body["provenance"]={**body["provenance"],"identity_contract":"canonical-envelope-v1"}
        digest=evidence_digest(canonical_evidence(**body))
        conn=FakeConnection(None,("EVD-PRIOR",digest))
        with patch.object(API,"db",lambda:connection(conn)):
            value=API.create(payload,authorization="Bearer unit-only-token")
        self.assertTrue(value["deduplicated"])
        self.assertIn("payload_hash=%s",conn.calls[1][0])

    def test_timezone_naive_evidence_cannot_be_ingested(self):
        with self.assertRaises(HTTPException) as result:
            API.create(event(observed_at="2026-10-20T06:00:00"),
                       authorization="Bearer unit-only-token")
        self.assertEqual(result.exception.status_code,422)

    def test_identity_contract_cannot_be_forged_by_caller(self):
        with self.assertRaises(HTTPException) as result:
            API.create(event(provenance={"synthetic":True,"identity_contract":"canonical-envelope-v1"}),
                       authorization="Bearer unit-only-token")
        self.assertEqual(result.exception.status_code,422)

    def test_search_limit_validation_does_not_access_database(self):
        with self.assertRaises(HTTPException) as result:
            API.search(limit=0,authorization="Bearer unit-only-token")
        self.assertEqual(result.exception.status_code,422)

    def test_unauthorized_ingestion_is_denied_before_any_database_io(self):
        with self.assertRaises(HTTPException) as result:
            API.create(event(),authorization="Bearer wrong")
        self.assertEqual(result.exception.status_code,401)

if __name__=="__main__":unittest.main()
