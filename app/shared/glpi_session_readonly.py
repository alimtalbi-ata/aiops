"""Server-owned GLPI REST v1 read-only session adapter.

Dedicated trusted HTTPS GLPI origin and server-owned credentials only. Session
is always closed after a ticket GET. No Portal route or ticket write methods.
"""
import json
from collections.abc import Callable
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler, ProxyHandler
from urllib.error import HTTPError, URLError


class GLPISessionReadBlocked(RuntimeError):
    pass


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def make_glpi_session_ticket_get(
    *, glpi_base_url: str, get_app_token: Callable, get_user_token: Callable,
    timeout: float = 3.0, max_bytes: int = 262144,
):
    """Return a GET-only callback compatible with make_core_glpi_readers.

    The supplied URL must be exactly /Ticket/{id} under glpi_base_url.
    Credential callbacks are server-owned and scoped by actor and tenant.
    """
    if (not callable(get_app_token) or not callable(get_user_token)
            or type(timeout) not in (int, float) or not 0 < timeout <= 10
            or type(max_bytes) is not int or not 1024 <= max_bytes <= 1048576):
        raise ValueError("glpi_session_dependencies_missing")
    try:
        if not isinstance(glpi_base_url, str) or len(glpi_base_url) > 512:
            raise ValueError("glpi_origin_invalid")
        base = urlsplit(glpi_base_url)
        port = base.port
        if (not isinstance(glpi_base_url, str) or base.scheme != "https"
                or not base.hostname or base.username is not None
                or base.password is not None or base.path or base.query
                or base.fragment or glpi_base_url.endswith("/") or port == 0
                or any(ord(c) <= 32 or ord(c) == 127 for c in glpi_base_url)
                or "\\" in glpi_base_url):
            raise ValueError("glpi_origin_invalid")
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError("glpi_origin_invalid") from exc
    opener = build_opener(ProxyHandler({}), _NoRedirect())
    origin = glpi_base_url.rstrip("/")

    def token(value):
        if (not isinstance(value, str) or not value or len(value) > 4096
                or any(ord(c) < 33 or ord(c) > 126 or c == "\\" for c in value)):
            raise GLPISessionReadBlocked("glpi_credentials_unavailable")
        return value

    def get_json(path, headers):
        request = Request(origin + "/apirest.php/" + path,
                          headers={**headers, "Accept": "application/json"},
                          method="GET")
        with opener.open(request, timeout=timeout) as response:
            if response.status != 200:
                raise GLPISessionReadBlocked("glpi_non_200")
            if "application/json" not in response.headers.get("Content-Type", "").lower():
                raise GLPISessionReadBlocked("glpi_non_json")
            raw = response.read(max_bytes + 1)
            if len(raw) > max_bytes:
                raise GLPISessionReadBlocked("glpi_response_too_large")
        result = json.loads(raw)
        if not isinstance(result, dict):
            raise GLPISessionReadBlocked("glpi_object_required")
        return result

    def safe_scope(value, limit):
        return (isinstance(value, str) and bool(value.strip())
                and len(value) <= limit
                and not any(ord(ch) < 32 or ord(ch) == 127 for ch in value))

    def get(*, url, actor, tenant_id, ticket_id=None, glpi_instance_id=None, **scope):
        prefix = origin + "/Ticket/"
        if isinstance(url, str) and url.startswith(prefix):
            url_ticket_id = url[len(prefix):]
        else:
            url_ticket_id = None
        if ticket_id is None:
            ticket_id = url_ticket_id
        if (not safe_scope(actor, 256)
                or not safe_scope(tenant_id, 128)
                or not isinstance(ticket_id, str) or not ticket_id.isascii()
                or not ticket_id.isdecimal() or not 1 <= len(ticket_id) <= 18
                or ticket_id.startswith("0") or url_ticket_id != ticket_id
                or not safe_scope(glpi_instance_id, 128)
                or url != origin + "/Ticket/" + ticket_id):
            raise GLPISessionReadBlocked("glpi_ticket_scope_invalid")
        session = None
        app = token(get_app_token(actor=actor, tenant_id=tenant_id,
                                  ticket_id=ticket_id, glpi_instance_id=glpi_instance_id))
        user = token(get_user_token(actor=actor, tenant_id=tenant_id,
                                    ticket_id=ticket_id, glpi_instance_id=glpi_instance_id))
        try:
            initial = get_json("initSession", {"App-Token": app,
                                                "Authorization": "user_token " + user})
            session = token(initial.get("session_token"))
            ticket = get_json("Ticket/" + ticket_id, {"App-Token": app,
                                                       "Session-Token": session})
            # Authentication does not establish the requested ticket identity.
            observed_id = ticket.get("id")
            if (type(observed_id) not in (str, int)
                    or str(observed_id) != ticket_id):
                raise GLPISessionReadBlocked("glpi_ticket_response_mismatch")
            return ticket
        except (HTTPError, URLError, TimeoutError, OSError, UnicodeError,
                ValueError, json.JSONDecodeError) as exc:
            raise GLPISessionReadBlocked("glpi_authenticated_read_failed") from exc
        finally:
            if session is not None:
                try:
                    get_json("killSession", {"App-Token": app, "Session-Token": session})
                except Exception as exc:
                    # An unclosed remote session cannot count as a successful read.
                    raise GLPISessionReadBlocked("glpi_session_cleanup_unconfirmed") from exc

    return get
