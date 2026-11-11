"""Static regression guard for the portal bootstrap UI boundary.

Source-contract test only: not a browser test, CI success is not E2E proof.
"""
from pathlib import Path

CLIENT = Path(__file__).resolve().parents[1] / "app/portal/portal_bootstrap_client.js"


def test_bootstrap_rejects_unqualified_tenant_and_live_claims():
    js = CLIENT.read_text(encoding="utf-8")
    for guard in (
        'data.tenant_acl_qualified !== true',
        'data.actor_identity_server_derived !== true',
        'data.runtime_authenticated !== false',
        'data.live_remediation_authorized !== false',
        'data.provenance !== "UNATTESTED_UPSTREAM_API_READ"',
    ):
        assert guard in js, f"Fail-closed contract removed: {guard}"
    assert 'if (!show(data))' in js


def test_bootstrap_discards_stale_response_after_json_parse():
    js = CLIENT.read_text(encoding="utf-8")
    # A newer load or explicit clear invalidates the in-flight generation.
    assert "generation += 1;" in js
    assert "const current = generation;" in js
    assert "const data = await response.json();" in js
    assert js.index("const data = await response.json();") < js.index(
        "if (current !== generation) return;", js.index("const data = await response.json();")
    ) < js.index("if (!show(data))")
    assert 'if (input) input.value = "";' in js


def test_bootstrap_never_renders_unverified_as_live():
    js = CLIENT.read_text(encoding="utf-8")
    assert '"READABLE_UNVERIFIED — aucune attestation LIVE"' in js
    assert 'cache: "no-store", credentials: "omit", redirect: "error"' in js
    assert "td.textContent = String(run[field] ?? \"UNKNOWN\").slice(0, 256);" in js
