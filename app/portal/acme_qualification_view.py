"""Public, static, non-authoritative ACME qualification view model.

This is a deliberately fixed safe default. It must not accept caller-provided
identity, receipts, service tokens, environment flags or runtime evidence.
"""
from __future__ import annotations

STAGES = (
    ("OBSERVE", "Déclaration synthétique uniquement"),
    ("CORRELATE", "Déclaration synthétique uniquement"),
    ("DIAGNOSE", "Déclaration synthétique uniquement"),
    ("POLICY", "Déclaration synthétique uniquement"),
    ("SIMULATED_ACTION", "Sans effet réel · pré-résolution"),
    ("VERIFY", "Résolution Core synthétique · non attestée"),
    ("AUDIT", "Historique Worker déclaré · non attesté"),
    ("REMEDIATION_EFFECT", "NON VÉRIFIÉ"),
    ("LEARN", "NON VÉRIFIÉ"),
)
SCENES = (
    ("NOC", "Route source candidate · navigateur non qualifié"),
    ("Signals", "Route source candidate · navigateur non qualifié"),
    ("Twin", "Route source candidate · navigateur non qualifié"),
    ("Analyst / Critic", "Route source candidate · navigateur non qualifié"),
    ("Policy / HITL", "Route source candidate · navigateur non qualifié"),
    ("ITSM / Worker", "NON IMPLÉMENTÉ"),
    ("Timeline", "Route source candidate · navigateur non qualifié"),
)


def public_qualification_snapshot() -> dict:
    """Return fresh, constant-only public metadata. Never read external data."""
    return {
        "schema": "aiops.acme-public-qualification-snapshot.v1",
        "scope": "ACME-TEST",
        "mode": "SIMULATION_ONLY",
        "status": "NO_GO",
        "authority": "STATIC_SOURCE_DECLARATION_ONLY",
        "runtime_e2e_verified": False,
        "viewer_acl_verified": False,
        "browser_verified": False,
        "deployed_sha_attested": False,
        "remediation_effect_verified": False,
        "learning_verified": False,
        "autonomous_execution_allowed": False,
        "stages": [list(row) for row in STAGES],
        "scenes": [list(row) for row in SCENES],
    }
