"""Public ACME qualification milestone contract: static and fail-closed.

No caller-provided status, runtime receipt, service I/O or authorization.
"""
from copy import deepcopy

_MILESTONES = (
    ("identity_acl", "Identité / ACL", "BLOCKED",
     "OIDC BFF côté serveur, acteur → tenant → run exact, tests 401/403/404"),
    ("deployed_provenance", "Traçabilité déployée", "NOT_VERIFIED",
     "SHA du code et image réellement déployés, attestation indépendante"),
    ("core_twin_join", "Core / Twin", "NOT_VERIFIED",
     "Jointure incident → run → service et lecture isolée autorisée"),
    ("seven_scenes", "Sept scènes", "NOT_VERIFIED",
     "Parcours Chromium authentifié sur sandbox approuvée ; ITSM / Worker absent"),
    ("remediation_verify", "Remédiation / Verify", "NOT_VERIFIED",
     "Effet observé après action autorisée, retour à un état sain mesuré"),
    ("audit_learn", "Audit / Learn", "NOT_VERIFIED",
     "Historique vérifiable, résultat et apprentissage réellement persistés"),
)


def public_milestone_contract() -> dict:
    return deepcopy({
        "schema": "aiops.acme-public-milestones.v1",
        "scope": "ACME-TEST",
        "status": "NO_GO",
        "authority": "STATIC_SOURCE_DECLARATION_ONLY",
        "runtime_e2e_verified": False,
        "viewer_acl_verified": False,
        "deployed_sha_attested": False,
        "remediation_effect_verified": False,
        "learning_verified": False,
        "autonomous_execution_allowed": False,
        "milestones": [
            {"id": mid, "label": label, "status": status, "required_proof": proof}
            for mid, label, status, proof in _MILESTONES
        ],
    })
