"""PostgreSQL integration test for model-evaluation idempotency.

Runs only against the disposable PostgreSQL service provisioned by the CI
migration job. Never points at a shared or production database.
"""
import os
import sys
import uuid
import unittest
from concurrent.futures import ThreadPoolExecutor
from fastapi import HTTPException

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "app"))
os.environ["AIOPS_INTERNAL_TOKEN"] = "postgres-integration-only-token"
os.environ["DATABASE_URL"] = os.environ.get("DATABASE_URL", "postgresql://aiops:ci-only-password@127.0.0.1:5432/aiops")

from core import main as CORE


def evaluation(evaluation_id, metrics=None):
    return CORE.ModelEvaluationIn(
        evaluation_id=evaluation_id,
        dataset_version="integration-synthetic-v1",
        dataset_hash="b" * 64,
        provider="ci", model="ci-deterministic",
        prompt_version="analyst-v2.2+critic-v2.4",
        policy_version="policy-v2.0", retrieval_version="none",
        sample_count=2, metrics=metrics if metrics is not None else {"grounding": 1.0},
        gate_decision="PASS", artifact_uri="reports/postgres-idempotency-integration.json",
    )


class PostgreSQLEvaluationIdempotencyTests(unittest.TestCase):
    def setUp(self):
        CORE.ADMIN = "postgres-integration-only-token"
        self.evaluation_id = "EVAL-CI-" + uuid.uuid4().hex

    def invoke(self, item):
        return CORE.create_model_evaluation(item, authorization="Bearer postgres-integration-only-token")

    def test_concurrent_replay_is_single_row_and_conflicts_on_changed_payload(self):
        item = evaluation(self.evaluation_id)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(self.invoke, (item, item)))

        self.assertEqual(sorted(result["idempotent"] for result in results), [False, True])
        replay = self.invoke(item)
        self.assertTrue(replay["idempotent"])

        with CORE.db() as connection:
            row = connection.execute(
                "select dataset_version,dataset_hash,provider,model,prompt_version,policy_version,retrieval_version,sample_count,metrics,gate_decision,artifact_uri from aiops.model_evaluation_runs where evaluation_id=%s",
                (self.evaluation_id,),
            ).fetchone()
            count = connection.execute(
                "select count(*) from aiops.model_evaluation_runs where evaluation_id=%s",
                (self.evaluation_id,),
            ).fetchone()[0]
        self.assertEqual(count, 1)
        self.assertEqual(row[0:8], (item.dataset_version,item.dataset_hash,item.provider,item.model,item.prompt_version,item.policy_version,item.retrieval_version,item.sample_count))
        self.assertEqual(row[8], item.metrics)
        self.assertEqual(row[9:], (item.gate_decision,item.artifact_uri))

        with self.assertRaises(HTTPException) as conflict:
            self.invoke(evaluation(self.evaluation_id, metrics={"grounding": 0.25}))
        self.assertEqual(conflict.exception.status_code, 409)


if __name__ == "__main__":
    unittest.main()
