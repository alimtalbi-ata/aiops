import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from shared.verified_principal_glpi_readonly import (
    VerifiedGLPIReadbackBlocked,
    make_verified_principal_glpi_readonly_qualifier,
)


ACTOR = "oidc:" + "f" * 64
ASSOCIATION = {
    "actor": ACTOR,
    "tenant_id": "tenant-a",
    "glpi_instance_id": "glpi-eu",
    "glpi_entity_id": "17",
    "ticket_id": "42",
    "incident_id": "INC-OPS-1234",
    "run_id": "RUN-ABCDEFGH1234",
}


def config():
    return dict(
        connect=lambda: None,
        secret=b"x" * 32,
        fetch_signed_event=lambda **_: None,
        authorize_glpi_native_acl=lambda **_: True,
        authorize_core_read=lambda **_: True,
        authorize_glpi_read=lambda **_: True,
        core_token=lambda **_: "core-service-token",
        glpi_app_token=lambda **_: "glpi-app-token",
        glpi_user_token=lambda **_: "glpi-user-token",
        core_base_url="https://core.example.invalid",
        glpi_base_url="https://glpi.example.invalid",
        clock=lambda: 1_800_000_000,
    )


def test_readonly_qualifier_accepts_only_bearer_and_ticket_and_uses_derived_scope():
    seen = {"resolver": [], "core": [], "glpi": []}

    def resolver_factory(**kwargs):
        assert kwargs["connect"] is not None
        assert kwargs["authorize_glpi_native_acl"] is config_acl
        def resolve(bearer, ticket):
            seen["resolver"].append((bearer, ticket))
            return dict(ASSOCIATION)
        return resolve

    cfg = config()
    config_acl = cfg["authorize_glpi_native_acl"]

    def readers_factory(**kwargs):
        def core(*, actor, tenant_id, run_id):
            seen["core"].append((actor, tenant_id, run_id))
            return {"run": {"run_id": run_id, "incident_id": "INC-OPS-1234", "mode": "DEMO"}}
        def glpi(*, actor, tenant_id, ticket_id, glpi_instance_id):
            seen["glpi"].append((actor, tenant_id, ticket_id, glpi_instance_id))
            return {"id": ticket_id, "entities_id": "17"}
        return core, glpi

    with patch("shared.verified_principal_glpi_readonly.make_json_get", return_value=lambda **_: {}), \
         patch("shared.verified_principal_glpi_readonly.make_glpi_session_ticket_get", return_value=lambda **_: {}), \
         patch("shared.verified_principal_glpi_readonly.make_core_glpi_readers", side_effect=readers_factory), \
         patch("shared.verified_principal_glpi_readonly.make_verified_principal_glpi_xref_resolver", side_effect=resolver_factory):
        qualify = make_verified_principal_glpi_readonly_qualifier(**cfg)
        result = qualify(bearer_token="opaque-bearer", ticket_id="42")

    assert result["status"] == "OIDC_AUTHENTICATED_READ_ONLY_XREF_MATCH"
    assert result["raw_readbacks_match"] is True
    assert result["copilot_query_performed"] is False
    assert result["hitl_proposal_created"] is False
    assert result["glpi_write_performed"] is False
    assert result["execution_allowed"] is False
    assert seen == {
        "resolver": [("opaque-bearer", "42")],
        "core": [(ACTOR, "tenant-a", "RUN-ABCDEFGH1234")],
        "glpi": [(ACTOR, "tenant-a", "42", "glpi-eu")],
    }


def test_missing_acl_provider_fails_during_construction():
    cfg = config()
    cfg["authorize_glpi_native_acl"] = None
    with pytest.raises(ValueError, match="verified_glpi_readonly_trust_dependencies_missing"):
        make_verified_principal_glpi_readonly_qualifier(**cfg)


def test_core_read_failure_stops_before_glpi_read():
    calls = []
    def resolver_factory(**kwargs):
        return lambda bearer, ticket: dict(ASSOCIATION)
    def readers_factory(**kwargs):
        def core(**_):
            calls.append("core")
            raise RuntimeError("Core unavailable")
        def glpi(**_):
            calls.append("glpi")
            return {"id": "42", "entities_id": "17"}
        return core, glpi

    with patch("shared.verified_principal_glpi_readonly.make_json_get", return_value=lambda **_: {}), \
         patch("shared.verified_principal_glpi_readonly.make_glpi_session_ticket_get", return_value=lambda **_: {}), \
         patch("shared.verified_principal_glpi_readonly.make_core_glpi_readers", side_effect=readers_factory), \
         patch("shared.verified_principal_glpi_readonly.make_verified_principal_glpi_xref_resolver", side_effect=resolver_factory):
        qualify = make_verified_principal_glpi_readonly_qualifier(**config())
        with pytest.raises(VerifiedGLPIReadbackBlocked):
            qualify(bearer_token="opaque-bearer", ticket_id="42")
    assert calls == ["core"]
