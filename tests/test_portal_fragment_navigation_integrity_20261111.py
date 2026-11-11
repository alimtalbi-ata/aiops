"""Differential upgrade guard: visible shell fragment links must resolve locally.

This checks existing navigation only; it never grants tenant/actor access.
"""
import importlib
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path

from fastapi.testclient import TestClient


class ShellLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = Counter()
        self.fragments = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if attributes.get("id"):
            self.ids[attributes["id"]] += 1
        if tag == "a" and attributes.get("href", "").startswith("#"):
            self.fragments.append(attributes["href"][1:])


def test_existing_portal_fragment_navigation_has_unique_targets(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "app"))
    portal = importlib.import_module("portal.main")

    def unexpected_upstream(*args, **kwargs):
        raise AssertionError("Anonymous shell must not query live upstreams")

    monkeypatch.setattr(portal, "get_json", unexpected_upstream)
    monkeypatch.setattr(portal, "post_json", unexpected_upstream)
    monkeypatch.setattr(portal, "read_portal_snapshot", unexpected_upstream)
    response = TestClient(portal.app, raise_server_exceptions=False).get("/")
    assert response.status_code == 200
    links = ShellLinks()
    links.feed(response.text)
    expected = {"runs", "twin", "copilot", "noc", "integrations"}
    assert expected <= set(links.fragments), "Existing shell navigation capability lost"
    for fragment in links.fragments:
        assert links.ids[fragment] == 1, (
            f"Fragment #{fragment} must resolve to exactly one element, "
            f"found {links.ids[fragment]}"
        )
    assert "UNKNOWN" in response.text
    assert "Golden DEMO — désactivé" in response.text
    assert response.headers["cache-control"] == "no-store"
