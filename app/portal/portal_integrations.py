"""Operator-configured navigation only; never proxy or attest upstream health.

The underlying component registry is a targeted reuse from PR #36. A configured
browser link is not an authenticated service observation or a mounted route.
"""
from __future__ import annotations

import html
import ipaddress
import os
from urllib.parse import urlsplit

from portal.platform_registry import build_portal_component_registry

LINK_ENV = {
    "n8n": "AIOPS_PORTAL_LINK_N8N",
    "thruk": "AIOPS_PORTAL_LINK_THRUK",
    "checkmk": "AIOPS_PORTAL_LINK_CHECKMK",
    "grafana": "AIOPS_PORTAL_LINK_GRAFANA",
    "glpi": "AIOPS_PORTAL_LINK_GLPI",
}
VISIBLE_INTEGRATIONS = ("thruk", "grafana", "n8n", "glpi", "checkmk")
# ipaddress.is_private includes documentation/benchmark/special-use networks.
# Browser HTTP opt-in is intentionally narrower: RFC1918 IPv4 and ULA IPv6.
PRIVATE_HTTP_NETWORKS = tuple(ipaddress.ip_network(cidr) for cidr in (
    "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "fc00::/7",
))


def validate_browser_link(value: str, *, allow_private_http: bool = False) -> str:
    """Accept only an explicit HTTPS URL or opted-in private-LAN HTTP URL."""
    if not isinstance(value, str) or not value or value.strip() != value:
        raise ValueError("invalid integration URL")
    if len(value) > 2048 or any(ord(ch) < 33 or ord(ch) == 127 for ch in value):
        raise ValueError("invalid integration URL")
    if "\\" in value:
        raise ValueError("invalid integration URL")
    parsed = urlsplit(value)
    if (parsed.scheme not in ("http", "https") or not parsed.hostname
            or parsed.username is not None or parsed.password is not None
            or parsed.query or parsed.fragment or not parsed.netloc):
        raise ValueError("invalid integration URL")
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("invalid integration URL") from exc
    if port == 0 or "%" in parsed.netloc:
        raise ValueError("invalid integration URL")
    if parsed.scheme == "http":
        if not allow_private_http:
            raise ValueError("HTTP integration URL requires explicit LAN opt-in")
        try:
            address = ipaddress.ip_address(parsed.hostname)
        except ValueError as exc:
            raise ValueError("HTTP integration URL must use private IP") from exc
        if not any(address in network for network in PRIVATE_HTTP_NETWORKS):
            raise ValueError("HTTP integration URL must use RFC1918/ULA IP")
    return value


def build_navigation(env=None, *, now_utc=None) -> dict:
    env = os.environ if env is None else env
    registry = build_portal_component_registry(now_utc=now_utc)
    allow_http = env.get("AIOPS_PORTAL_ALLOW_HTTP_LINKS") == "true"
    for item in registry["items"]:
        item["external_url"] = None
        item["external_link_state"] = "NOT_APPLICABLE"
        setting = LINK_ENV.get(item["id"])
        if setting is None:
            continue
        item["external_link_state"] = "UNCONFIGURED"
        raw = env.get(setting, "")
        if not raw:
            continue
        try:
            item["external_url"] = validate_browser_link(raw, allow_private_http=allow_http)
            item["external_link_state"] = "CONFIGURED_UNVERIFIED"
        except ValueError:
            item["external_link_state"] = "REJECTED_CONFIGURATION"
        # Never promote a link to an authenticated or healthy observation.
        item["state"] = "UNKNOWN"
        item["runtime_authenticated"] = False
        item["route_mounted"] = False
        item["available_in_portal"] = False
    registry["navigation_mode"] = "EXTERNAL_BROWSER_LINKS_ONLY_NO_PROXY"
    registry["runtime_verified"] = False
    return registry


def render_navigation_html(registry: dict) -> str:
    items = {item["id"]: item for item in registry["items"]}
    result = ['<section class="panel" id="integrations"><h2>Intégrations</h2>',
              '<p class="muted">Liens configurés, jamais une preuve de disponibilité. '
              'État runtime : UNKNOWN. Aucun proxy ni accès automatique.</p><ul>']
    for ident in VISIBLE_INTEGRATIONS:
        item = items[ident]
        label = html.escape(item["name"], quote=True)
        url = item["external_url"]
        if url:
            safe = html.escape(url, quote=True)
            result.append('<li><a target="_blank" rel="noopener noreferrer" '
                          'referrerpolicy="no-referrer" href="' + safe + '">' + label
                          + '</a> — CONFIGURED_UNVERIFIED / UNKNOWN</li>')
        else:
            result.append('<li>' + label + ' — ' +
                          html.escape(item["external_link_state"], quote=True)
                          + ' / UNKNOWN</li>')
    result.append("</ul></section>")
    return "".join(result)
