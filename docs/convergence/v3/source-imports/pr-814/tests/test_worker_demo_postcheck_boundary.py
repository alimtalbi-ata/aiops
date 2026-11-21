"""Worker must never turn synthetic DEMO evidence into VERIFY PASS/RESOLVE."""
import ast
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / "app" / "worker" / "main.py"


def _stage_body():
    module = ast.parse(SOURCE.read_text())
    fn = next(node for node in module.body
              if isinstance(node, ast.AsyncFunctionDef) and node.name == "execute_stage")
    return ast.get_source_segment(SOURCE.read_text(), fn)


def test_demo_verify_blocks_before_synthetic_evidence_and_completion():
    body = _stage_body()
    guard = body.index("if mode in ('DEMO', 'REPLAY', 'STORY') and stage == 'VERIFY':")
    evidence = body.index("ev=post_json(EVID")
    complete = body.index("'event_type':'STAGE_COMPLETED'")
    assert guard < evidence < complete
    branch = body[guard:evidence]
    for marker in ("INDEPENDENT_POSTCHECK_MISSING", "'status':'BLOCKED'",
                   "'command':'BLOCK'", "'actual_recovery_state':'UNKNOWN'",
                   "'independent_runtime_postcheck_verified':False",
                   "'live_remediation_authorized':False", "return {"):
        assert marker in branch
    assert "STAGE_COMPLETED" not in branch


def test_workflow_stops_on_block_before_finish():
    import asyncio
    from test_worker_temporal_workflow_stop import _workflow_with_stub

    events = []
    result = asyncio.run(_workflow_with_stub(events, block_stage="VERIFY").run({
        "run_id": "demo-run-01", "mode": "DEMO", "scenario_id": "acme",
        "version": 0,
    }))
    assert result["status"] == "BLOCKED"
    assert result["blocked_stage"] == "VERIFY"
    assert events[-1][1]["stage"] == "VERIFY"
    assert not any(name == "finish_run" for name, _ in events)
