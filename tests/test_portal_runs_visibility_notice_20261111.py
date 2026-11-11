"""Source contract: all validated Runs remain visible, bounded by the envelope gate."""
from pathlib import Path

CLIENT = Path(__file__).resolve().parents[1] / "app/portal/portal_bootstrap_client.js"


def test_complete_bounded_runs_visibility_preserves_acl_fence():
    js = CLIENT.read_text(encoding="utf-8")
    assert "data.runs.items.length > 100" in js
    assert "for (const run of data.runs.items)" in js
    assert "data.runs.items.slice(0, 15)" not in js
    assert "data.tenant_acl_qualified !== true" in js
    assert "data.actor_identity_server_derived !== true" in js
    assert 'td.textContent = String(run[field] ?? "UNKNOWN").slice(0, 256);' in js
