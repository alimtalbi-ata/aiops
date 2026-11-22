import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from shared.hitl_identity import IdentityError
from shared.verified_principal import principal_from_bearer


def test_principal_is_derived_only_from_verified_oidc_claims():
    claims = {
        "subject_id": "oidc:" + "a" * 64,
        "issuer": "https://id.example.invalid/tenant",
        "roles": ["operator", "operator"],
        "groups": ["group-stable"],
        "mapping_version": "groups-v3",
        "jti": "jti-unique",
        "expires_at": 2_000_000_000,
        "simulated": False,
    }
    with patch("shared.verified_principal.verify_oidc_assertion", return_value=claims) as verify:
        principal = principal_from_bearer("opaque-bearer", is_revoked=lambda **_: False)
    verify.assert_called_once_with("opaque-bearer")
    assert principal.actor_id == claims["subject_id"]
    assert principal.roles == ("operator",)
    assert principal.groups == ("group-stable",)
    assert principal.mapping_version == "groups-v3"
    assert principal.simulated is False


@pytest.mark.parametrize("field,value", [
    ("subject_id", "browser:admin"),
    ("issuer", "http://untrusted.invalid"),
    ("roles", []),
    ("groups", []),
    ("jti", ""),
    ("expires_at", True),
    ("simulated", True),
])
def test_invalid_or_simulated_verified_claims_never_create_principal(field, value):
    claims = {
        "subject_id": "oidc:" + "b" * 64,
        "issuer": "https://id.example.invalid/tenant",
        "roles": ["operator"],
        "groups": ["group-stable"],
        "mapping_version": "groups-v3",
        "jti": "jti-unique",
        "expires_at": 2_000_000_000,
        "simulated": False,
    }
    claims[field] = value
    with patch("shared.verified_principal.verify_oidc_assertion", return_value=claims):
        with pytest.raises(IdentityError, match="verified_principal_claims_invalid"):
            principal_from_bearer("opaque-bearer", is_revoked=lambda **_: False)


def test_oidc_verifier_failure_is_propagated_without_fallback():
    with patch(
        "shared.verified_principal.verify_oidc_assertion",
        side_effect=IdentityError("oidc_assertion_verification_failed"),
    ):
        with pytest.raises(IdentityError, match="oidc_assertion_verification_failed"):
            principal_from_bearer("invalid", is_revoked=lambda **_: False)


def test_revoked_or_unavailable_jti_store_never_issues_principal():
    claims = {
        "subject_id": "oidc:" + "c" * 64, "issuer": "https://id.example.invalid",
        "roles": ["operator"], "groups": ["group"], "mapping_version": "v1",
        "jti": "revoked-jti", "expires_at": 2_000_000_000, "simulated": False,
    }
    with patch("shared.verified_principal.verify_oidc_assertion", return_value=claims):
        with pytest.raises(IdentityError, match="oidc_assertion_revoked_or_store_unavailable"):
            principal_from_bearer("token", is_revoked=lambda **_: True)
        with pytest.raises(IdentityError, match="oidc_assertion_revoked_or_store_unavailable"):
            principal_from_bearer("token", is_revoked=lambda **_: None)
        with pytest.raises(IdentityError, match="oidc_revocation_check_failed"):
            principal_from_bearer("token", is_revoked=lambda **_: (_ for _ in ()).throw(RuntimeError("db down")))
