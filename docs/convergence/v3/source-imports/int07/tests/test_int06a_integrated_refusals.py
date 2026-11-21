"""Offline real B result -> C refusal boundary + A presentation. No runtime."""
import copy
import pytest
from test_acme_runtime_context import RuntimeContextTests
from portal.acme_runtime_context import qualify_context, digest
from portal.acme_workbench_presentation import render_runtime_refusals
from worker.int06a_contract import refuse_unattested_context, utc

@pytest.mark.parametrize("case,verdict,reason", [
    ("nominal","BLOCK","INJECTED_READBACKS_NOT_ATTESTED"),
    ("registry","BLOCK","SOURCE_REGISTRY_MISSING"),
    ("snapshot","REJECT","SNAPSHOT_MISMATCH"),
    ("impact","REJECT","IDENTITY_MISMATCH:twin"),
    ("attempt","REJECT","IDENTITY_MISMATCH:twin"),
    ("missing","BLOCK","AUTHORITY_MISSING:twin"),
    ("stale","BLOCK","STALE_OBSERVATION"),
    ("future","REJECT","FUTURE_OBSERVATION"),
])
def test_real_context_refusal(case, verdict, reason):
    f = RuntimeContextTests()
    f.setUp()
    if case == "registry": f.registry = None
    if case == "snapshot": f.rows["twin"]["snapshot_id"] = "FOREIGN"
    if case in ("impact","attempt"):
        key = "impact_incident_id" if case == "impact" else "attempt_id"
        f.rows["twin"]["content"][key] = "FOREIGN"
        f.rows["twin"]["content_sha256"] = digest(f.rows["twin"]["content"])
    if case == "missing": del f.rows["twin"]
    if case == "stale": f.rows["twin"]["observed_at"] = "2026-10-25T08:00:00Z"
    if case == "future": f.rows["twin"]["observed_at"] = "2026-10-25T09:00:30.000001Z"
    result = f.qualify()
    assert (result["qualification"], result["reason"]) == (verdict, reason)
    with pytest.raises(ValueError, match="context_" + verdict.lower()):
        refuse_unattested_context(result)
    html = render_runtime_refusals(result)
    assert ("UNKNOWN — BLOCK" if verdict == "BLOCK" else "FAIL — REJECT") in html
    assert "Terminal C : MISSING" in html
    assert "RESOLVED" not in html and "LIVE : NO-GO" in html

@pytest.mark.parametrize("claim", [None, "UNKNOWN", "PASS", "ALLOW", "attested", "live"])
def test_untrusted_consumer_result(claim):
    f = RuntimeContextTests()
    f.setUp()
    result = f.qualify()
    if claim is None: result = None
    elif claim == "attested": result["runtime_attested"] = True
    elif claim == "live": result["live_remediation_authorized"] = True
    else: result["qualification"] = claim
    with pytest.raises(ValueError, match="context_missing|context_unqualified"):
        refuse_unattested_context(result)
    html = render_runtime_refusals(result)
    assert "Qualification runtime : UNKNOWN" in html and "RESOLVED" not in html

@pytest.mark.parametrize("stamp", ["2026-10-25T09:00:00Z","2026-10-25T09:00:00.123456Z"])
def test_utc_preserved(stamp):
    f = RuntimeContextTests()
    f.setUp()
    f.rows["twin"]["observed_at"] = stamp
    result = f.qualify()
    assert result["evidence"][1]["observed_at"] == stamp
    assert utc(stamp).microsecond == (123456 if "." in stamp else 0)
    with pytest.raises(ValueError, match="context_block"):
        refuse_unattested_context(result)


# Exercise the existing workflow loop with activity stubs; no Temporal server.
# The stub is a test seam, not a deployed B-to-Worker adapter.
import asyncio
from test_worker_temporal_transition_receipts import workflow_for
from test_int06a_contract import manifest_fixture, FIXTURE_INTENT
from worker.int06a_contract import validate_manifest, validate_postcheck, digest as c_digest

@pytest.mark.parametrize("case", ["BC01","BC02","BC03","BC04","BC05","BC06","BC07","BC08","BC09","BC10","BC12"])
def test_workflow_refusal_has_no_downstream_scheduling(case):
    f = RuntimeContextTests()
    f.setUp()
    if case == "BC02": f.registry = None
    if case == "BC03": f.rows["twin"]["snapshot_id"] = "FOREIGN"
    if case in ("BC04","BC05"):
        key = "impact_incident_id" if case == "BC04" else "attempt_id"
        f.rows["twin"]["content"][key] = "FOREIGN"
        f.rows["twin"]["content_sha256"] = digest(f.rows["twin"]["content"])
    if case == "BC06": del f.rows["twin"]
    context = f.qualify()
    if case == "BC07": context = None
    if case == "BC08": context["qualification"] = "PASS"
    # Build the synchronous fixture before entering the workflow event loop.
    terminal_fixture = manifest_fixture() if case in ("BC09","BC10","BC12") else None
    events = []
    refusals = []
    def gate(args):
        assert args["stage"] == "POLICY"
        if case in ("BC09","BC10","BC12"):
            manifest, readback = terminal_fixture
            if case == "BC09":
                readback.pop("terminal")
            elif case == "BC10":
                readback["terminal"]["identity"]["run_id"] = "FOREIGN"
                manifest["terminal"] = copy.deepcopy(readback["terminal"])
                readback["terminal_readback_sha256"] = c_digest(readback["terminal"])
            else:
                readback["postcheck_verified"] = False
            with pytest.raises(ValueError, match="postcheck_unqualified|terminal_unqualified") as denied:
                if case == "BC12":
                    validate_postcheck(intent=FIXTURE_INTENT, independently_read=readback)
                else:
                    validate_manifest(manifest, expected_sha="a"*40, intent=FIXTURE_INTENT, independently_read=readback)
            refusals.append(str(denied.value))
        with pytest.raises(ValueError, match="context_missing|context_unqualified|context_block|context_reject") as denied:
            refuse_unattested_context(context)
        refusals.append(str(denied.value))
        return {"run_id":args["run_id"], "stage":args["stage"],
                "status":"BLOCKED", "version":args["version"]+1}
    instance = workflow_for(gate, events)
    result = asyncio.run(instance.run({"run_id":f.i["run_id"],"mode":"DEMO",
                                       "scenario_id":"acme","version":0}))
    assert result["status"] == "BLOCKED" and result["blocked_stage"] == "POLICY"
    assert [name for name,_ in events] == ["start_run","execute_stage"]
    assert [a["stage"] for name,a in events if name == "execute_stage"] == ["POLICY"]
    assert refusals
    assert "RESOLVED" not in render_runtime_refusals(context)
    assert "Terminal C : MISSING" in render_runtime_refusals(context)
