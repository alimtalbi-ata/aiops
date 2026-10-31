#!/usr/bin/env python3
"""Qualify a configured OpenAI-compatible NVIDIA NIM endpoint without leaking credentials."""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen


MARKER = "AIOPS2_NIM_OK"


def safe_base_url(raw: str) -> str:
    parsed = urlsplit(raw.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("NIM_BASE_URL must be an absolute http(s) URL")
    if parsed.username or parsed.password:
        raise ValueError("Do not embed credentials in NIM_BASE_URL")
    if parsed.query or parsed.fragment:
        raise ValueError("NIM_BASE_URL must not contain query or fragment")
    path = parsed.path.rstrip("/")
    if path.endswith("/v1"):
        path = path[:-3]
    return urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))


def request_json(url: str, payload: dict | None, timeout: float) -> tuple[dict, float, int]:
    headers = {"Accept": "application/json"}
    data = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode("utf-8")
    request = Request(url, data=data, headers=headers, method="POST" if data else "GET")
    started = time.monotonic()
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read(2_000_000)
            elapsed_ms = round((time.monotonic() - started) * 1000, 2)
            if response.status < 200 or response.status >= 300:
                raise RuntimeError(f"HTTP_{response.status}")
            return json.loads(raw.decode("utf-8")), elapsed_ms, response.status
    except HTTPError as exc:
        raise RuntimeError(f"HTTP_{exc.code}") from None
    except URLError as exc:
        reason = getattr(exc, "reason", None)
        raise RuntimeError(f"CONNECTION_ERROR:{type(reason).__name__}") from None
    except TimeoutError:
        raise RuntimeError("TIMEOUT") from None
    except json.JSONDecodeError:
        raise RuntimeError("INVALID_JSON") from None


def qualify(base_url: str, model: str, timeout: float) -> dict:
    report = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "provider": "nim",
        "base_url": base_url,
        "model": model,
        "status": "FAIL",
        "models_api": {"status": "NOT_RUN"},
        "completion_api": {"status": "NOT_RUN"},
        "usage": None,
        "credential_value_recorded": False,
    }
    try:
        models, elapsed, status = request_json(
            f"{base_url}/v1/models", None, timeout
        )
        available = [
            item.get("id") for item in models.get("data", [])
            if isinstance(item, dict) and isinstance(item.get("id"), str)
        ]
        selected_model = model
        if not selected_model:
            nemotron_120b = [
                item for item in available
                if "nemotron" in item.lower() and ("120b" in item.lower() or "120-b" in item.lower())
            ]
            if len(nemotron_120b) == 1:
                selected_model = nemotron_120b[0]
            elif len(available) == 1:
                selected_model = available[0]
            else:
                report["models_api"] = {
                    "status": "MODEL_SELECTION_REQUIRED",
                    "http_status": status,
                    "latency_ms": elapsed,
                    "available_model_ids": available,
                }
                report["error"] = "Set NIM_MODEL to one of the model IDs listed by /v1/models"
                return report
        report["model"] = selected_model
        report["models_api"] = {
            "status": "PASS" if selected_model in available else "MODEL_NOT_LISTED",
            "http_status": status,
            "latency_ms": elapsed,
            "model_count": len(available),
            "requested_model_found": selected_model in available,
        }
        if selected_model not in available:
            report["error"] = "Configured model ID not found in /v1/models"
            return report

        payload = {
            "model": selected_model,
            "messages": [
                {"role": "system", "content": "You are a runtime connectivity probe. Follow the user instruction exactly."},
                {"role": "user", "content": f"Reply with exactly this token and no other text: {MARKER}"},
            ],
            "temperature": 0,
            "max_tokens": 48,
        }
        answer, elapsed, status = request_json(
            f"{base_url}/v1/chat/completions", payload, timeout
        )
        choices = answer.get("choices", [])
        content = ""
        if choices and isinstance(choices[0], dict):
            message = choices[0].get("message", {})
            if isinstance(message, dict):
                content = str(message.get("content", "")).strip()
        marker_found = MARKER in content
        usage = answer.get("usage")
        safe_usage = None
        if isinstance(usage, dict):
            safe_usage = {
                key: usage.get(key)
                for key in ("prompt_tokens", "completion_tokens", "total_tokens")
                if isinstance(usage.get(key), (int, float))
            }
        report["usage"] = safe_usage
        report["completion_api"] = {
            "status": "PASS" if marker_found else "UNEXPECTED_MODEL_RESPONSE",
            "http_status": status,
            "latency_ms": elapsed,
            "probe_marker_found": marker_found,
            "finish_reason": choices[0].get("finish_reason") if choices and isinstance(choices[0], dict) else None,
        }
        report["status"] = "PASS" if marker_found else "FAIL"
        if not marker_found:
            report["error"] = "Completion returned but did not reproduce the probe marker"
        return report
    except (RuntimeError, ValueError) as exc:
        report["error"] = str(exc)
        return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=os.getenv("NIM_BASE_URL", "http://10.79.94.31:8000/v1"))
    parser.add_argument("--model", default=os.getenv("NIM_MODEL", ""))
    parser.add_argument("--timeout", type=float, default=float(os.getenv("NIM_TIMEOUT_SECONDS", "30")))
    parser.add_argument("--report", default="artifacts/nim-runtime-qualification.json")
    args = parser.parse_args()

    if not args.base_url:
        print("CONFIG_ERROR: set NIM_BASE_URL.", file=sys.stderr)
        return 2
    if args.timeout <= 0 or args.timeout > 300:
        print("CONFIG_ERROR: timeout must be between 0 and 300 seconds.", file=sys.stderr)
        return 2

    try:
        base = safe_base_url(args.base_url)
    except ValueError as exc:
        print(f"CONFIG_ERROR: {exc}", file=sys.stderr)
        return 2

    result = qualify(base, args.model, args.timeout)
    rendered = json.dumps(result, indent=2, sort_keys=True)
    print(rendered)
    report_path = args.report
    if report_path:
        os.makedirs(os.path.dirname(report_path) or ".", exist_ok=True)
        with open(report_path, "w", encoding="utf-8") as stream:
            stream.write(rendered + "\n")
        os.chmod(report_path, 0o600)
        print(f"REPORT_WRITTEN={report_path}")
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
