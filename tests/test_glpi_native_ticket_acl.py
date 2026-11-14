import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from shared.glpi_native_ticket_acl import make_glpi_native_ticket_acl


def test_native_acl_reads_exact_ticket_as_oidc_actor_and_checks_entity():
    seen = []
    def reader_factory(**kwargs):
        def read(**scope):
            seen.append(scope)
            return {"id": "42", "entities_id": "17"}
        return read

    with patch("shared.glpi_native_ticket_acl.make_glpi_session_ticket_get",
               side_effect=reader_factory) as factory:
        authorize = make_glpi_native_ticket_acl(
            glpi_base_url="https://glpi.example.invalid",
            get_app_token=lambda **_: "app",
            get_actor_user_token=lambda **_: "actor-user-token",
        )

    assert authorize(
        actor="oidc:subject-hash", tenant_id="tenant-a",
        glpi_instance_id="glpi-eu", glpi_entity_id="17",
        ticket_id="42", action="read_ticket",
    ) is True
    assert factory.call_args.kwargs["get_actor_user_token"] is not None
    assert seen == [{
        "url": "https://glpi.example.invalid/Ticket/42",
        "actor": "oidc:subject-hash",
        "tenant_id": "tenant-a",
        "ticket_id": "42",
        "glpi_instance_id": "glpi-eu",
    }]


def test_native_acl_denies_entity_mismatch_and_upstream_permission_denial():
    with patch("shared.glpi_native_ticket_acl.make_glpi_session_ticket_get",
               return_value=lambda **_: {"id": "42", "entities_id": "18"}):
        authorize = make_glpi_native_ticket_acl(
            glpi_base_url="https://glpi.example.invalid",
            get_app_token=lambda **_: "app",
            get_actor_user_token=lambda **_: "actor-token",
        )
    args = dict(
        actor="oidc:subject", tenant_id="tenant-a",
        glpi_instance_id="glpi-eu", glpi_entity_id="17",
        ticket_id="42", action="read_ticket",
    )
    assert authorize(**args) is False

    with patch("shared.glpi_native_ticket_acl.make_glpi_session_ticket_get",
               return_value=lambda **_: (_ for _ in ()).throw(PermissionError("GLPI 403"))):
        authorize = make_glpi_native_ticket_acl(
            glpi_base_url="https://glpi.example.invalid",
            get_app_token=lambda **_: "app",
            get_actor_user_token=lambda **_: "actor-token",
        )
    assert authorize(**args) is False


def test_native_acl_rejects_non_read_action_and_malformed_scope_before_upstream():
    with patch("shared.glpi_native_ticket_acl.make_glpi_session_ticket_get") as reader:
        authorize = make_glpi_native_ticket_acl(
            glpi_base_url="https://glpi.example.invalid",
            get_app_token=lambda **_: "app",
            get_actor_user_token=lambda **_: "actor-token",
        )
    args = dict(
        actor="oidc:subject", tenant_id="tenant-a",
        glpi_instance_id="glpi-eu", glpi_entity_id="17",
        ticket_id="42", action="write_ticket",
    )
    assert authorize(**args) is False
    assert reader.call_count == 1  # construction only; no upstream read
    args["action"] = "read_ticket"
    args["ticket_id"] = "../42"
    assert authorize(**args) is False
