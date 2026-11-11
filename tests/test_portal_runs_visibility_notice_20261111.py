"""Source contract: never silently present a truncated Runs preview as complete."""
from pathlib import Path

CLIENT = Path(__file__).resolve().parents[1] / "app/portal/portal_bootstrap_client.js"


def test_bounded_runs_preview_explicitly_discloses_hidden_entries():
    js = CLIENT.read_text(encoding="utf-8")
    assert "data.runs.items.slice(0, 15)" in js
    assert "if (data.runs.items.length > 15)" in js
    assert '"Aperçu limité : 15 sur " + data.runs.items.length' in js
    assert '" Runs reçus (lecture non attestée). D\'autres Runs ne sont pas affichés."' in js
    assert "td.colSpan = 5;" in js
    assert "rows.appendChild(tr);" in js
    assert "data.tenant_acl_qualified !== true" in js
    assert "data.actor_identity_server_derived !== true" in js
