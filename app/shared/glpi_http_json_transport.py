"""Authenticated JSON GET transport for server-injected GLPI/Core readers.

Caller must supply a trusted server-side token provider. No user-supplied
URLs, credentials, TLS bypass, redirects or writes. This is not installed in
Portal and does not grant tenant/actor ACL.
"""
import json
from collections.abc import Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, HTTPRedirectHandler


class ReadTransportBlocked(RuntimeError):
    pass


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def make_json_get(*, get_token: Callable, timeout: float = 3.0,
                  max_bytes: int = 262144):
    if (not callable(get_token) or type(timeout) not in (int, float)
            or not 0 < timeout <= 10 or type(max_bytes) is not int
            or not 1024 <= max_bytes <= 1048576):
        raise ValueError("secure_http_transport_configuration_required")
    opener = build_opener(_NoRedirect())

    def get(*, url, actor, tenant_id, **scope):
        if (not isinstance(url, str) or not url.startswith("https://")
                or any(c in url for c in ("#", "@", "\\", "\r", "\n"))):
            raise ReadTransportBlocked("trusted_https_url_required")
        if not isinstance(actor, str) or not actor.strip() or not isinstance(tenant_id, str) or not tenant_id.strip():
            raise ReadTransportBlocked("actor_tenant_required")
        try:
            token = get_token(actor=actor, tenant_id=tenant_id, **scope)
            if (not isinstance(token, str) or not token or len(token) > 4096
                    or any(ord(c) < 33 or ord(c) > 126 or c == "\\\\" for c in token)):
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
