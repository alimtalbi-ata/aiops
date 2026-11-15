"""Script-free HTML for offline computed NOC projection."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from aiops2_noc_decision_html import render_computed_noc_html
from aiops2_noc_decision import build_noc_decision

NOW = "2026-11-15T12:00:00Z"


def projection():
    event = {"tenant_id": "acme", "source": "checkmk", "source_event_id": "san-1",
             "ci_id": "san-01", "service_id": "payments", "severity": "P1",
             "evidence_sha256": "a" * 64, "observed_at": "2026-11-15T11:59:00Z",
             "known_at": "2026-11-15T11:59:05Z"}
    edge = {"tenant_id": "acme", "from_id": "san-01", "to_id": "payments",
            "source_id": "synthetic-cmdb", "evidence_sha256": "b" * 64,
            "observed_at": "2026-11-15T11:59:00Z"}
    return build_noc_decision([event], [edge], as_of=NOW)


def test_computed_projection_renders_as_simulation():
    html = render_computed_noc_html(projection())
    assert "SIMULATION" in html
    assert "DENY_LIVE" in html
    assert "san-01 → payments" in html
    assert "<script" not in html.lower()


def test_unknown_path_is_explicit():
    p = projection()
    p["decisions"][0]["impact_state"] = "UNKNOWN"
    p["decisions"][0]["impact_paths"] = []
    p["decisions"][0]["analyst"]["impact_state"] = "UNKNOWN"
    p["decisions"][0]["critic"]["disposition"] = "NEEDS_MORE_EVIDENCE"
    p["decisions"][0]["next_noc_action"] = "COLLECT_MISSING_DEPENDENCY_EVIDENCE"
    assert "UNKNOWN" in render_computed_noc_html(p)


def test_html_escapes_untrusted_identity():
    p = projection()
    p["decisions"][0]["incident_id"] = "<img src=x onerror=alert(1)>"
    html = render_computed_noc_html(p)
    assert "<img" not in html
    assert "&lt;img" in html


@pytest.mark.parametrize("key,value", [
    ("mode", "LIVE"), ("runtime_attested", True),
    ("live_remediation_authorized", True), ("schema", "unknown")
])
def test_unqualified_projection_rejected(key, value):
    p = projection()
    p[key] = value
    with pytest.raises(ValueError):
        render_computed_noc_html(p)


def test_unqualified_decision_rejected():
    p = projection()
    p["decisions"][0]["policy_disposition"] = "ALLOW_LIVE"
    with pytest.raises(ValueError):
        render_computed_noc_html(p)



@pytest.mark.parametrize("mutation", [
    lambda d: d["critic"].update(disposition="NEEDS_MORE_EVIDENCE"),
    lambda d: d["critic"].update(runtime_attested=True),
    lambda d: d["analyst"].update(impact_state="UNKNOWN"),
    lambda d: d["impact_paths"][0].update(nodes=["san-01", None]),
    lambda d: d["impact_paths"][0].update(nodes=["san-01"]),
])
def test_renderer_rejects_contradictory_or_malformed_evidence(mutation):
    p = projection()
    mutation(p["decisions"][0])
    with pytest.raises(ValueError):
        render_computed_noc_html(p)



@pytest.mark.parametrize("action", [
    "EXECUTE_REMEDIATION", "ALLOW_LIVE", "COLLECT_MISSING_DEPENDENCY_EVIDENCE", None
])
def test_renderer_refuses_action_inconsistent_with_sourced_impact(action):
    p = projection()
    p["decisions"][0]["next_noc_action"] = action
    with pytest.raises(ValueError, match="contradictory_noc_next_action"):
        render_computed_noc_html(p)



@pytest.mark.parametrize("mutation", [
    lambda path: path.update(nodes=["san-01", "unrelated-service"]),
    lambda path: path.update(nodes=["san-01", "san-01", "payments"],
                             evidence_sha256=["b" * 64, "b" * 64]),
    lambda path: path.update(evidence_sha256=[]),
    lambda path: path.update(evidence_sha256=["not-a-digest"]),
    lambda path: path.update(evidence_sha256=[None]),
])
def test_renderer_refuses_unsourced_or_forged_path_provenance(mutation):
    p = projection()
    mutation(p["decisions"][0]["impact_paths"][0])
    with pytest.raises(ValueError, match="invalid_noc_path"):
        render_computed_noc_html(p)



def test_renderer_rejects_excessive_decision_count():
    p = projection()
    p["decisions"] = p["decisions"] * 101
    with pytest.raises(ValueError, match="decision_budget_exceeded"):
        render_computed_noc_html(p)


def test_renderer_rejects_excessive_path_count():
    p = projection()
    item = p["decisions"][0]
    item["impact_paths"] = item["impact_paths"] * 101
    with pytest.raises(ValueError, match="path_budget_exceeded"):
        render_computed_noc_html(p)


def test_renderer_rejects_excessive_path_depth():
    p = projection()
    path = p["decisions"][0]["impact_paths"][0]
    path["nodes"] = ["san-01"] + [f"hop-{i}" for i in range(100)] + ["payments"]
    path["evidence_sha256"] = ["b" * 64] * (len(path["nodes"]) - 1)
    with pytest.raises(ValueError, match="invalid_noc_path"):
        render_computed_noc_html(p)



@pytest.mark.parametrize("field", ["runtime_attested", "live_remediation_authorized"])
def test_renderer_fails_closed_when_projection_guard_is_missing(field):
    p = projection()
    del p[field]
    with pytest.raises(ValueError, match="unqualified_noc_projection"):
        render_computed_noc_html(p)


@pytest.mark.parametrize("field", ["runtime_attested", "live_remediation_authorized"])
def test_renderer_fails_closed_when_decision_guard_is_missing(field):
    p = projection()
    del p["decisions"][0][field]
    with pytest.raises(ValueError, match="unqualified_noc_decision"):
        render_computed_noc_html(p)


def test_renderer_escapes_untrusted_path_nodes():
    p = projection()
    path = p["decisions"][0]["impact_paths"][0]
    path["nodes"] = ["<img src=x onerror=alert(1)>", "payments"]
    html = render_computed_noc_html(p)
    assert "<img" not in html
    assert "&lt;img" in html


def test_renderer_accepts_valid_sha256_evidence_on_synthetic_path():
    """A well-formed SHA-256 must not be rejected by the end anchor."""
    p = projection()
    p["decisions"][0]["impact_paths"][0]["evidence_sha256"] = ["0123456789abcdef" * 4]
    html = render_computed_noc_html(p)
    assert "san-01 → payments" in html


def test_renderer_rejects_sha256_with_trailing_backslash_z():
    """The end anchor must not be interpreted as a literal backslash-Z."""
    p = projection()
    p["decisions"][0]["impact_paths"][0]["evidence_sha256"] = ["a" * 64 + r"\Z"]
    with pytest.raises(ValueError, match="invalid_noc_path"):
        render_computed_noc_html(p)


@pytest.mark.parametrize("node", ["x" * 257, "é" * 257])
def test_renderer_rejects_oversized_path_node(node):
    p = projection()
    p["decisions"][0]["impact_paths"][0]["nodes"] = [node, "payments"]
    with pytest.raises(ValueError, match="invalid_noc_path"):
        render_computed_noc_html(p)


def test_renderer_accepts_path_node_at_length_boundary():
    p = projection()
    p["decisions"][0]["impact_paths"][0]["nodes"] = ["x" * 256, "payments"]
    assert "x" * 256 in render_computed_noc_html(p)


@pytest.mark.parametrize("field", ["incident_id", "tenant_id", "service_id", "priority"])
def test_renderer_rejects_oversized_display_metadata(field):
    p = projection()
    p["decisions"][0][field] = "X" * 257
    with pytest.raises(ValueError, match="invalid_noc_display_metadata"):
        render_computed_noc_html(p)


@pytest.mark.parametrize("field", ["incident_id", "tenant_id", "service_id", "priority"])
def test_renderer_accepts_display_metadata_at_boundary(field):
    p = projection()
    p["decisions"][0][field] = "X" * 256
    if field == "service_id":
        p["decisions"][0]["impact_paths"][0]["nodes"][-1] = "X" * 256
    assert "X" * 256 in render_computed_noc_html(p)


@pytest.mark.parametrize("field", ["incident_id", "tenant_id", "service_id", "priority"])
def test_renderer_rejects_nonstring_display_metadata(field):
    p = projection()
    p["decisions"][0][field] = 123
    with pytest.raises(ValueError, match="invalid_noc_display_metadata"):
        render_computed_noc_html(p)
