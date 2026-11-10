"""Server-owned read-only HTTP adapters for canonical Core/GLPI observations.

No default endpoints, tokens, network calls or tenant authority. Deployment
must provide trusted service endpoints, per-request server ACL and credentials.
These readers return raw JSON only; the signed-xref comparison remains required.
"""
import re
from collections.abc import Callable
from urllib.parse import quote, urlsplit


class GLPIHTTPReadBlocked(RuntimeError):
    pass


def make_core_glpi_readers(
    *, core_base_url: str, glpi_base_url: str,
    core_get: Callable, glpi_get: Callable,
    authorize_read: Callable,
):
    """Create GET-only adapters with server-owned clients.

    core_get/glpi_get(url=..., actor=..., tenant_id=...) must be server
    implementations enforcing TLS, authentication, timeouts and no redirects.
    authorize_read must check actor+tenant+resource ACL and return exactly True.
    """
    origins = []
    for base in (core_base_url, glpi_base_url):
        if not isinstance(base, str) or len(base) > 512:
            raise ValueError("trusted_https_endpoint_required")
        try:
            parsed = urlsplit(base)
            port = parsed.port
        except ValueError as exc:
            raise ValueError("trusted_https_endpoint_required") from exc
        if (parsed.scheme != "https" or not parsed.hostname
                or parsed.username is not None or parsed.password is not None
                or parsed.path or parsed.query or parsed.fragment
                or base.endswith("/") or port == 0
                or any(ch.isspace() or ord(ch) < 33 or ord(ch) == 127
                       for ch in base)
                or "\\" in base):
            raise ValueError("trusted_https_endpoint_required")
        origins.append((parsed.hostname.lower(), port or 443))
    if origins[0] == origins[1]:
        raise ValueError("core_glpi_service_origins_must_differ")
    if not all(callable(fn) for fn in (core_get, glpi_get, authorize_read)):
        raise ValueError("authenticated_read_dependencies_missing")

    def safe_scope(value, limit):
        return (isinstance(value, str) and bool(value.strip())
                and len(value) <= limit
                and not any(ord(ch) < 32 or ord(ch) == 127 for ch in value))

    def require_scope(actor, tenant_id):
        if not safe_scope(actor, 256) or not safe_scope(tenant_id, 128):
            raise GLPIHTTPReadBlocked("missing_actor_tenant_scope")

    def read_core_raw(*, actor, tenant_id, run_id):
        require_scope(actor, tenant_id)
        if (not isinstance(run_id, str)
                or not re.fullmatch(r"RUN-[A-Z0-9]{8,64}", run_id)):
            raise GLPIHTTPReadBlocked("invalid_run_id")
        if authorize_read(actor=actor, tenant_id=tenant_id,
                          resource="core_run", resource_id=run_id) is not True:
            raise GLPIHTTPReadBlocked("core_read_acl_denied")
        return core_get(url=core_base_url + "/api/runs/" + quote(run_id),
                        actor=actor, tenant_id=tenant_id)

    def read_glpi_raw(*, actor, tenant_id, ticket_id, glpi_instance_id):
        require_scope(actor, tenant_id)
        if (not isinstance(ticket_id, str) or not ticket_id.isascii()
                or not ticket_id.isdecimal() or not 1 <= len(ticket_id) <= 18
                or ticket_id.startswith("0")
                or not safe_scope(glpi_instance_id, 128)):
            raise GLPIHTTPReadBlocked("invalid_glpi_identity")
        if authorize_read(actor=actor, tenant_id=tenant_id,
                          resource="glpi_ticket", resource_id=ticket_id,
                          glpi_instance_id=glpi_instance_id) is not True:
            raise GLPIHTTPReadBlocked("glpi_read_acl_denied")
        return glpi_get(url=glpi_base_url + "/Ticket/" + quote(ticket_id),
                        actor=actor, tenant_id=tenant_id,
                        glpi_instance_id=glpi_instance_id)

    return read_core_raw, read_glpi_raw
