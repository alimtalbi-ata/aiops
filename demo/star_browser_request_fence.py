"""Pure, offline HTTP request fence for STAR browser evidence capture.

This is an authorization *filter*, not a guarantee that GET is side-effect free.
It never performs HTTP, DNS resolution, browser navigation, or LIVE actions.
"""
from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlsplit

_RESOURCE_TYPES = frozenset({"stylesheet", "script", "font", "image", "xhr", "fetch"})


def canonical_origin(url: str) -> str:
    """Refuse userinfo, fragments, malformed and noncanonical HTTP origins."""
    if not isinstance(url, str) or len(url) > 2048 or "\\" in url or any(c.isspace() for c in url):
        raise ValueError("unsafe URL")
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError as exc:
        raise ValueError("invalid port") from exc
    if (parts.scheme not in ("http", "https") or not parts.hostname
            or parts.username is not None or parts.password is not None
            or parts.fragment or parts.hostname.endswith(".") or port == 0
            or parts.netloc != parts.netloc.lower()):
        raise ValueError("noncanonical origin")
    return f"{parts.scheme}://{parts.netloc}"


@dataclass(frozen=True)
class ReadOnlyRequestPolicy:
    event_url: str
    allowed_origin: str
    reviewed_get_urls: tuple[str, ...] = ()

    def validate(self) -> None:
        if canonical_origin(self.event_url) != self.allowed_origin:
            raise ValueError("event origin not approved")
        if canonical_origin(self.allowed_origin) != self.allowed_origin:
            raise ValueError("approved origin not canonical")
        urls = self.reviewed_get_urls
        if not isinstance(urls, tuple) or len(urls) > 32 or len(set(urls)) != len(urls):
            raise ValueError("invalid GET allowlist")
        for url in urls:
            if canonical_origin(url) != self.allowed_origin or url == self.event_url:
                raise ValueError("GET allowlist must contain exact same-origin subresources")

    def permits(self, *, url: str, method: str, navigation: bool,
                main_frame: bool, resource_type: str) -> bool:
        """Only exact main-page GET or explicitly reviewed same-origin GET.

        A caller MUST abort and record every denied request. Successful checks
        do not authenticate a page, an event, HITL or a business outcome.
        """
        try:
            self.validate()
            if method != "GET" or canonical_origin(url) != self.allowed_origin:
                return False
            if navigation:
                return main_frame and url == self.event_url
            return resource_type in _RESOURCE_TYPES and url in self.reviewed_get_urls
        except (TypeError, ValueError):
            return False
