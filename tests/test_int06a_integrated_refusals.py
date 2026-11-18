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
