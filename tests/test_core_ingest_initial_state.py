"""Isolated contract for Core's actual create() body; no database or network writes."""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]


class RecordingCursor:
    def __init__(self, existing=None):
        self.existing = existing
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, sql, params):
        self.calls.append((sql, params))
        return self

    def fetchone(self):
        return self.existing


def run_create(mode="DEMO", existing=None):
    """Compile the real Core create function with inert injected collaborators."""
    source = ROOT / "app/core/main.py"
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "create")
    node.decorator_list = []
    cursor = RecordingCursor(existing)
    events = []
    from shared.domain import STAGES, initial_stage_state
    namespace = {
        "RunIn": object,
        "Header": lambda default=None: None,
        "auth": lambda token: None,
        "bearer": lambda value: value,
        "db": lambda: cursor,
        "new": lambda kind: "RUN-TEST-INGEST",
        "STAGES": STAGES,
        "initial_stage_state": initial_stage_state,
        "append_event": lambda *args, **kwargs: events.append((args, kwargs)),
    }
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(source), "exec"), namespace)
    payload = SimpleNamespace(mode=mode, incident_id="INC-TEST", scenario_id="SCN-GOLDEN-PAYMENT-P1", idempotency_key="test-ingest")
    result = namespace["create"](payload, authorization="test-only")
    return result, cursor.calls, events, STAGES


class InitialIngestStageTests(unittest.TestCase):
    def test_ingest_pass_and_completed_at_only_for_ingest(self):
        result, calls, events, stages = run_create()
        self.assertEqual(result["status"], "CREATED")
        inserts = [(sql, params) for sql, params in calls if sql.startswith("insert into aiops.run_stage_state")]
        self.assertEqual(len(inserts), len(stages))
        self.assertEqual([params[1] for _, params in inserts], stages)
        for sql, params in inserts:
            self.assertIn("completed_at", sql)
            self.assertIn("case when %s='PASS' then now() else null end", sql)
            self.assertEqual(params[0], "RUN-TEST-INGEST")
            self.assertEqual(params[2], "PASS" if params[1] == "INGEST" else "PENDING")
            self.assertEqual(params[3], params[2])
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0][0][2:5], ("INGEST", "RUN_CREATED", "CREATED"))
        self.assertEqual(events[0][1]["payload"]["mode"], "DEMO")

    def test_other_modes_keep_worker_stages_pending(self):
        for mode in ("LIVE", "REPLAY", "STORY"):
            with self.subTest(mode=mode):
                _, calls, events, stages = run_create(mode)
                inserts = [p for sql, p in calls if sql.startswith("insert into aiops.run_stage_state")]
                self.assertEqual(len(inserts), len(stages))
                self.assertEqual(sum(p[2] == "PASS" for p in inserts), 1)
                self.assertEqual(events[0][1]["payload"]["mode"], mode)

    def test_idempotent_existing_run_is_not_mutated(self):
        row = ("RUN-EXISTING", "DEMO", "SCN-GOLDEN-PAYMENT-P1", "RESOLVED", 3)
        result, calls, events, _ = run_create(existing=row)
        self.assertEqual(result["run_id"], "RUN-EXISTING")
        self.assertEqual(result["status"], "RESOLVED")
        self.assertEqual(len(calls), 1)
        self.assertEqual(events, [])


if __name__ == "__main__":
    unittest.main()
