"""Explicit read-only assembly of the signed GLPI/Core comparison chain.

No defaults, runtime registration, network access or authorization grant.
The deployment owns all trust inputs and both service identities.
"""
from collections.abc import Callable

from shared.glpi_hmac_qualification import make_hmac_glpi_qualifier
from shared.glpi_http_json_transport import make_json_get
from shared.glpi_http_readers import make_core_glpi_readers


def make_server_glpi_readonly_qualifier(
    *, secret: bytes, fetch_signed_event: Callable,
    consume_nonce: Callable, authorize_actor: Callable,
    authorize_read: Callable, core_token: Callable, glpi_token: Callable,
    core_base_url: str, glpi_base_url: str,
    clock: Callable | None = None,
):
    """Compose server-injected trust, ACL, transport and signed comparison.

    The caller must install a real signed event source, atomic nonce store,
    per-actor/tenant ACLs and distinct authenticated service credentials.
    This function never grants Copilot/HITL access or GLPI writes.
    """
    if not all(callable(fn) for fn in (
            fetch_signed_event, consume_nonce, authorize_actor,
            authorize_read, core_token, glpi_token)):
        raise ValueError("server_trust_dependencies_missing")
    # Validate the xref trust root before allocating transport adapters.
    if not isinstance(secret, bytes) or len(secret) < 32:
        raise ValueError("xref_signing_key_missing")
    core_get = make_json_get(get_token=core_token, allowed_origin=core_base_url)
    glpi_get = make_json_get(get_token=glpi_token, allowed_origin=glpi_base_url)
    read_core_raw, read_glpi_raw = make_core_glpi_readers(
        core_base_url=core_base_url, glpi_base_url=glpi_base_url,
        core_get=core_get, glpi_get=glpi_get,
        authorize_read=authorize_read,
    )
    return make_hmac_glpi_qualifier(
        secret=secret, fetch_signed_event=fetch_signed_event,
        consume_nonce=consume_nonce, authorize_actor=authorize_actor,
        read_core_raw=read_core_raw, read_glpi_raw=read_glpi_raw,
        clock=clock,
    )
