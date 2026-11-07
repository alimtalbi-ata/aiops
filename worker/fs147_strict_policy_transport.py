"""Strict FS147 Policy transport boundary (opt-in until remote attestation exists).

The remote service must echo the full scope. Never normalize an unattested
response into a successful decision. No network or filesystem side effects.
"""
from worker.fs147_policy_attestation import require_policy_attestation


def attested_policy_transport(post_check):
    """Wrap authenticated post_check(payload) for the FS147 service adapter.

    The outgoing Policy payload is legacy-shaped; the embedding transport must
    bind it to the authenticated run context and obtain a remotely attested
    response. The transport must NOT synthesize correlation fields locally.
    """
    def call(request, evidence_id, payload):
        reply = post_check(request, evidence_id, payload)
        return require_policy_attestation(reply, request, evidence_id)
    return call


def strict_policy_step(request, observation, analysis, critique, *, post_check):
    """Fail closed before the legacy adapter can backfill missing identities."""
    from worker.fs147_policy_adapter import check_fs147_policy
    wrapped = attested_policy_transport(post_check)
    return check_fs147_policy(
        request, observation, analysis, critique,
        post_check=lambda payload: wrapped(request, observation["evidence_id"], payload),
    )
