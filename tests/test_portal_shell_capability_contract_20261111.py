"""Regression contract for the existing portal shell, without runtime dependencies.

This test checks discoverability only. It does not authorize any tenant-scoped
read model or assert that a backend feature is operational.
"""
import importlib
from pathlib import Path

from fastapi.testclient import TestClient


def test_existing_portal_shell_preserves_discovery_without_claiming_live_data(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "app"))
    portal = importlib.import_module("portal.main")

    def forbidden(*args, **kwargs):
        raise AssertionError("Anonymous shell must not query Core/Twin/Copilot")

    monkeypatch.setattr(portal, "get_json", forbidden)
    monkeypatch.setattr(portal, "post_json", forbidden)
    monkeypatch.setattr(portal, "read_portal_snapshot", forbidden)

    response = TestClient(portal.app, raise_server_exceptions=False).get("/")
    assert response.status_code == 200
    html = response.text

    # Navigation and major existing capabilities must remain discoverable.
    for target in (
        'href="#runs"', 'href="#twin"', 'href="#copilot"',
        'href="#noc"', 'href="#integrations"', 'href="/itsm"',
        'href="/demo/acme-impact"', 'href="/demo/explore-story"',
    ):
        assert target in html, f"Missing portal navigation capability: {target}"

    # Explicit uncertainty and safe operator gating are part of the contract.
    assert 'id="portal-states"' in html
    assert 'id="portal-runs"' in html
    assert 'id="portal-twin"' in html
    assert "UNKNOWN" in html
    assert 'id="run-detail-open"' in html
    assert 'disabled aria-disabled="true"' in html
    assert "Golden DEMO — désactivé" in html
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
