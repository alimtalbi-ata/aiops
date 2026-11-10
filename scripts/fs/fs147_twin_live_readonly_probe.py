"""Read-only Twin FS147/SAN live API qualification probe.

Never mutates Core, Twin, Docker, Policy or Evidence. Requires independently
verified Core RUN IDs. A fixture result is not a Debian E2E receipt.
"""
import argparse
import json
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler


class _RejectRedirects(HTTPRedirectHandler):
    """Never forward the Twin bearer credential to a redirect destination."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


from fs147_twin_partition_gate import IsolationError, qualify


def fetch_json(base_url, path, token, timeout=8, opener=None):
    parsed = urlsplit(base_url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc or parsed.username or parsed.password:
        raise IsolationError("invalid Twin API base URL")
    if not token:
        raise IsolationError("Twin read token missing")
    request = Request(base_url.rstrip("/") + path,
                      headers={"Authorization": "Bearer " + token,
                               "Accept": "application/json"}, method="GET")
    # Default urllib redirects can leak the bearer token to another origin.
    # A qualification capture must never follow redirects.
    if opener is None:
        opener = build_opener(_RejectRedirects()).open
    try:
        with opener(request, timeout=timeout) as response:
            if response.status != 200:
                raise IsolationError("Twin API returned non-200 status")
            if response.headers.get_content_type() != "application/json":
                raise IsolationError("Twin API returned non-JSON content type")
            raw = response.read(2_000_001)
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise IsolationError("Twin API request unavailable: " + type(exc).__name__) from exc
    if len(raw) > 2_000_000:
        raise IsolationError("Twin API response exceeds size limit")
    try:
        return json.loads(raw)
    except (ValueError, UnicodeDecodeError) as exc:
        raise IsolationError("Twin API returned invalid JSON") from exc


def qualify_live(base_url, token, fs_namespace, san_namespace, fs_run, san_run, fetch=fetch_json):
    if not isinstance(fs_run, str) or not isinstance(san_run, str) or not fs_run.strip() or not san_run.strip() or fs_run == san_run:
        raise IsolationError("two distinct independent Core RUN IDs required")
    if any(ch in run for run in (fs_run, san_run) for ch in ("/", "?", "#", "\\", "\n", "\r")):
        raise IsolationError("unsafe Core RUN ID")
    graph = fetch(base_url, "/api/twin/graph", token)
    fs = fetch(base_url, "/api/twin/scenario/" + quote(fs_run, safe="") + "/facts", token)
    san = fetch(base_url, "/api/twin/scenario/" + quote(san_run, safe="") + "/facts", token)
    result = qualify(graph, fs, san, fs_namespace, san_namespace, fs_run, san_run)
    result["source"] = "Twin HTTP GET (read-only)"
    result["qualification"] = "API_CAPTURE_ONLY_NOT_DEBIAN_E2E"
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--twin-url", required=True)
    parser.add_argument("--fs-namespace", required=True)
    parser.add_argument("--san-namespace", required=True)
    parser.add_argument("--fs-run-id", required=True)
    parser.add_argument("--san-run-id", required=True)
    args = parser.parse_args()
    try:
        result = qualify_live(args.twin_url, os.getenv("AIOPS_TWIN_READ_TOKEN", ""),
                              args.fs_namespace, args.san_namespace,
                              args.fs_run_id, args.san_run_id)
    except (IsolationError, KeyError, TypeError, ValueError) as exc:
        print(json.dumps({"status": "HOLD", "reason": str(exc)}))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
