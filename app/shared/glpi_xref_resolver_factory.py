"""Wire the concrete HMAC verifier to the canonical xref boundary.

The signing key, nonce store and ACL evaluator MUST be server-installed
dependencies. This factory performs no I/O, stores no secrets and does not
mount a Portal/Copilot route. Do not use in production without a durable,
atomic replay store and authenticated event fetch.
"""
from collections.abc import Callable
from shared.glpi_signed_xref_boundary import resolve_signed_glpi_xref
from shared.glpi_xref_hmac_verifier import verify_hmac_xref_event


def make_hmac_canonical_xref_resolver(
    *, secret: bytes, fetch_signed_event: Callable,
    consume_nonce: Callable, authorize_actor: Callable,
    clock: Callable | None = None,
):
    """Return a server-only resolver; fail closed if any trust input is absent."""
    if (not isinstance(secret, bytes) or len(secret) < 32
            or not all(callable(fn) for fn in
                       (fetch_signed_event, consume_nonce, authorize_actor))
            or (clock is not None and not callable(clock))):
        raise ValueError("xref_trust_dependencies_missing")

    def verify(*, event, actor, tenant_id, ticket_id):
        return verify_hmac_xref_event(
            event=event, actor=actor, tenant_id=tenant_id,
            ticket_id=ticket_id, secret=secret,
            consume_nonce=consume_nonce, authorize_actor=authorize_actor,
            now=clock() if clock is not None else None,
        )

    def resolve(*, actor, tenant_id, ticket_id):
        return resolve_signed_glpi_xref(
            actor=actor, tenant_id=tenant_id, ticket_id=ticket_id,
            fetch_signed_event=fetch_signed_event,
            verify_event_and_acl=verify,
        )

    return resolve
