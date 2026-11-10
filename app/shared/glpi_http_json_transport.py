"""Authenticated JSON GET transport for server-injected GLPI/Core readers.

Caller must supply a trusted server-side token provider. No user-supplied
URLs, credentials, TLS bypass, redirects or writes. This is not installed in
Portal and does not grant tenant/actor ACL.
"""
import json
from collections.abc import Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.parse import urlsplit


class ReadTransportBlocked(RuntimeError):
    pass


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def make_json_get(*, get_token: Callable, allowed_origin: str,
                  timeout: float = 3.0, max_bytes: int = 262144):
    if (not callable(get_token) or type(timeout) not in (int, float)
            or not 0 < timeout <= 10 or type(max_bytes) is not int
            or not 1024 <= max_bytes <= 1048576):
        raise ValueError("secure_http_transport_configuration_required")
    try:
        trusted = urlsplit(allowed_origin)
        trusted_port = trusted.port
        if (trusted.scheme != "https" or not trusted.hostname
                or trusted.username is not None or trusted.password is not None
                or trusted.path or trusted.query or trusted.fragment
                or any(c.isspace() or ord(c) < 33 for c in allowed_origin)
                or "\\" in allowed_origin):
            raise ValueError("trusted_origin_required")
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError("trusted_origin_required") from exc
    opener = build_opener(_NoRedirect())

    def get(*, url, actor, tenant_id, **scope):
        if (not isinstance(url, str) or not url.startswith("https://")
                or any(c in url for c in ("#", "@", "\\", "\r", "\n"))):
            raise ReadTransportBlocked("trusted_https_url_required")
        try:
            parsed = urlsplit(url)
            request_port = parsed.port
            same_origin = (parsed.scheme == "https" and parsed.hostname
                           and parsed.hostname.lower() == trusted.hostname.lower()
                           and (request_port or 443) == (trusted_port or 443)
                           and parsed.username is None and parsed.password is None)
        except (ValueError, TypeError):
            same_origin = False
        if not same_origin:
            raise ReadTransportBlocked("untrusted_upstream_origin")
        if not isinstance(actor, str) or not actor.strip() or not isinstance(tenant_id, str) or not tenant_id.strip():
            raise ReadTransportBlocked("actor_tenant_required")
        try:
            token = get_token(actor=actor, tenant_id=tenant_id, **scope)
            if (not isinstance(token, str) or not token or len(token) > 4096
                    or any(ord(c) < 33 or ord(c) > 126 or ord(c) == 92 for c in token)):
                raise ReadTransportBlocked("server_credential_unavailable")
            req = Request(url, headers={"Authorization": "Bearer " + token,
                                        "Accept": "application/json"},
                          method="GET")
            with opener.open(req, timeout=timeout) as response:
                if response.status != 200:
                    raise ReadTransportBlocked("upstream_non_200")
                if "application/json" not in response.headers.get("Content-Type", "").lower():
                    raise ReadTransportBlocked("upstream_non_json")
                data = response.read(max_bytes + 1)
                if len(data) > max_bytes:
                    raise ReadTransportBlocked("upstream_response_too_large")
            result = json.loads(data)
            if not isinstance(result, dict):
                raise ReadTransportBlocked("upstream_json_object_required")
            return result
        except (HTTPError, URLError, TimeoutError, OSError, UnicodeError,
                ValueError, json.JSONDecodeError) as exc:
            raise ReadTransportBlocked("authenticated_upstream_read_failed") from exc

    return get
