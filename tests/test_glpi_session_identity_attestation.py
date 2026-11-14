"""GLPI session identity must match the verified actor binding before GET Ticket."""
import io
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from shared.glpi_session_readonly import (
    GLPISessionReadBlocked, make_glpi_session_ticket_get,
)


class Response:
    status = 200
    headers = {"Content-Type": "application/json"}
    def __init__(self, value):
        self.data = io.BytesIO(json.dumps(value).encode())
    def __enter__(self): return self
    def __exit__(self, *_): return False
    def read(self, n): return self.data.read(n)


class Opener:
    def __init__(self, identity):
        self.identity = identity
        self.paths = []
    def open(self, request, timeout):
        path = request.full_url.split("/apirest.php/")[-1]
        self.paths.append(path)
        if path == "initSession":
            assert request.get_header("Authorization") == "user_token actor-secret"
            return Response({"session_token": "ci-session"})
        assert request.get_header("Session-token") == "ci-session"
        if path == "getFullSession":
            return Response(self.identity)
        if path == "Ticket/42":
            return Response({"id": 42, "entities_id": 7})
        if path == "killSession":
            return Response({})
        raise AssertionError(path)


def read(identity, credential=None):
    opener = Opener(identity)
    with patch("shared.glpi_session_readonly.build_opener", return_value=opener):
        getter = make_glpi_session_ticket_get(
            glpi_base_url="https://glpi.example.invalid",
            get_app_token=lambda **_: "app-secret",
            get_user_token=lambda **_: credential if credential is not None else {
                "user_token": "actor-secret", "glpi_user_id": 17,
            },
            require_session_user_identity=True,
        )
    try:
        result = getter(
            url="https://glpi.example.invalid/Ticket/42",
            actor="oidc:actor", tenant_id="tenant-a",
            ticket_id="42", glpi_instance_id="glpi-a",
        )
        return result, opener.paths
    except GLPISessionReadBlocked:
        return None, opener.paths


def test_glpi_session_user_identity_matches_before_ticket_read():
    result, paths = read({"session": {"glpiID": 17}})
    assert result["id"] == 42
    assert paths == ["initSession", "getFullSession", "Ticket/42", "killSession"]


@pytest.mark.parametrize("identity", [
    {"session": {"glpiID": 18}},
    {"session": {"glpiID": True}},
    {"session": {"glpiID": "017"}},
    {"session": {}},
    {"session": []},
    {"glpiID": 17},
])
def test_mismatch_or_missing_glpi_identity_denies_and_closes_session(identity):
    result, paths = read(identity)
    assert result is None
    assert paths == ["initSession", "getFullSession", "killSession"]


def test_plain_token_not_accepted_in_strict_identity_mode():
    result, paths = read({"session": {"glpiID": 17}}, "actor-secret")
    assert result is None
    assert paths == []
