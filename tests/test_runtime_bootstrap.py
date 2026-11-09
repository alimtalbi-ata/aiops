"""Real SDK sandbox and psycopg cursor contracts; no remote service required."""
import datetime
import importlib
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))


class WorkerBootstrapTests(unittest.IsolatedAsyncioTestCase):
    async def test_production_workflow_prepares_in_real_temporal_sandbox(self):
        from temporalio import workflow
        from temporalio.worker.workflow_sandbox import SandboxedWorkflowRunner
        with patch.dict(os.environ, {'AIOPS_INTERNAL_TOKEN': 'isolated-runtime-test-token'}):
            main = importlib.import_module('worker.main')
        definition = workflow._Definition.must_from_class(main.IncidentWorkflow)
        # Importing FastAPI/requests with the workflow previously failed here.
        SandboxedWorkflowRunner().prepare_workflow(definition)
        self.assertEqual(main.RETRY.maximum_interval, datetime.timedelta(seconds=10))
        self.assertEqual(main.RETRY.maximum_attempts, 3)

    async def test_replay_recorded_isolated_demo_workflow(self):
        from temporalio.client import WorkflowHistory
        from temporalio.worker import Replayer
        from worker.workflow import IncidentWorkflow
        fixture = Path(__file__).parent / 'fixtures/temporal/incident-demo-local-history.json'
        history = WorkflowHistory.from_json('RUN-36A9512212F364E6', fixture.read_text())
        await Replayer(workflows=[IncidentWorkflow]).replay_workflow(history)


class CoreCursorTests(unittest.TestCase):
    def test_stage_update_reads_existing_attempt_from_execute_cursor(self):
        with patch.dict(os.environ, {'AIOPS_INTERNAL_TOKEN': 'isolated-runtime-test-token'}):
            main = importlib.import_module('core.main')
        # psycopg Connection has execute; fetchone belongs to its returned cursor.
        for current, expected in (((4,), 4), (None, 0)):
            with self.subTest(current=current):
                connection = Mock(spec=['execute'])
                cursor = Mock()
                cursor.fetchone.return_value = current
                connection.execute.return_value = cursor
                main.set_stage(connection, 'RUN-LOCALTEST', 'NORMALIZE', 'RUNNING')
                cursor.fetchone.assert_called_once_with()
                self.assertEqual(connection.execute.call_args.args[1][3], expected)
