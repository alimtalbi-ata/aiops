"""Bounded JSON GET and Core POST for the isolated loopback LAB, never a remote transport."""
import json
import math
import socket
import threading
from http.client import HTTPConnection, HTTPException
from time import monotonic


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _finite(value):
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("nonfinite JSON number")
    return number


def get_json(port, token, path, *, timeout=5, limit=65536):
    return _request_json(port, token, path, method="GET", body=None, timeout=timeout, limit=limit)


def post_core_json(port, token, path, body, *, timeout=5, limit=65536):
    """Only the two synthetic Core creation routes; never retry a write."""
    if path not in ("/api/incidents", "/api/runs") or type(body) is not dict:
        raise ValueError("invalid Core publication")
    raw = json.dumps(body, allow_nan=False).encode("utf-8")
    if len(raw) > 65536:
        raise ValueError("Core request too large")
    return _request_json(port, token, path, method="POST", body=raw, timeout=timeout, limit=limit)


def _request_json(port, token, path, *, method, body, timeout, limit):
    if type(port) is not int or not 1024 <= port <= 65535 or port in {7770, 7777, 7790}:
        raise ValueError("invalid isolated lab port")
    if not isinstance(token, str) or not 32 <= len(token) <= 256 or any(not 33 <= ord(c) <= 126 for c in token):
        raise ValueError("invalid internal token")
    if not isinstance(path, str) or not path.startswith("/api/") or any(not 33 <= ord(c) <= 126 for c in path) or "#" in path:
        raise ValueError("invalid API path")
    if type(timeout) not in (int, float) or not 0 < timeout <= 5 or type(limit) is not int or not 0 < limit <= 65536:
        raise ValueError("invalid transport bounds")
    deadline = monotonic() + timeout
    conn = HTTPConnection("127.0.0.1", port, timeout=timeout)
    timer = None
    response = None
    try:
        conn.connect()
        sock = conn.sock
        def interrupt():
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
        remaining = deadline - monotonic()
        if remaining <= 0:
            raise ValueError("HTTP deadline")
        timer = threading.Timer(remaining, interrupt)
        timer.daemon = True
        timer.start()
        headers = {"Authorization": "Bearer " + token, "Accept": "application/json", "Connection": "close"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        conn.request(method, path, body=body, headers=headers)
        response = conn.getresponse()
        if response.status != 200:
            raise ValueError("HTTP read unavailable")
        if response.headers.defects:
            raise ValueError("malformed HTTP response headers")
        lengths = response.headers.get_all("Content-Length", [])
        if response.headers.get_all("Transfer-Encoding") or len(lengths) > 1:
            raise ValueError("unsupported HTTP framing")
        declared = None
        if lengths:
            value = lengths[0]
            if not value.isascii() or not value.isdecimal() or len(value) > 10:
                raise ValueError("invalid HTTP length")
            declared = int(value)
            if declared > limit:
                raise ValueError("HTTP bounds exceeded")
        raw = response.read(limit + 1)
        if declared is not None and len(raw) != declared:
            raise ValueError("truncated HTTP response")
        if len(raw) > limit or monotonic() >= deadline:
            raise ValueError("HTTP bounds exceeded")
        data = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs, parse_constant=_finite, parse_float=_finite)
        if type(data) is not dict:
            raise ValueError("JSON object required")
        return data
    except (OSError, HTTPException, RecursionError) as exc:
        raise ValueError("HTTP read unavailable") from exc
    finally:
        if timer is not None:
            timer.cancel()
            timer.join()
        if response is not None:
            response.close()
        conn.close()
