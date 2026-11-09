"""Read-only Core case collector for AIOps2 integration.

Fetches actual Core run and evidence documents; never invokes command/execute,
policy-record, events or reconciliation POST endpoints. Output is a correlation
envelope, NOT a claim of verified GLPI linkage or end-to-end success.
"""
import argparse
import json
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen


def _get_json(base_url, path, token=None, timeout=5):
    url = base_url.rstrip("/") + path
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    req = Request(url, headers=headers, method="GET")
    with urlopen(req, timeout=timeout) as response:
        return json.load(response)


def collect(run_id, base_url="http://127.0.0.1:810", token=None, timeout=5):
    if not isinstance(run_id, str) or not run_id.startswith("RUN-") or not all(
        c.isalnum() or c == "-" for c in run_id
    ):
        raise ValueError("invalid run ID")
    parsed = urlsplit(base_url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("invalid Core URL")
    if parsed.hostname not in ("127.0.0.1", "localhost", "::1") and parsed.scheme != "https":
        raise ValueError("non-local Core URL requires HTTPS")
    rid = quote(run_id, safe="-")
    envelope = {
        "schema": "aiops2-core-case-context-v1",
        "source": "core_http_get",
        "read_only": True,
        "run_id": run_id,
        "status": "HOLD",
        "checks": {},
        "incident_id": None,
        "run_status": None,
        "evidence_observed": False,
        "glpi_link_verified": False,
        "worker_execution_verified": False,
        "reason_codes": [],
    }
    try:
        run = _get_json(base_url, "/api/runs/" + rid, token, timeout)
        if not isinstance(run, dict):
            raise ValueError("Core run response is not an object")
        actual_id = run.get("run_id") or run.get("id")
        if actual_id != run_id:
            raise ValueError("Core run ID mismatch")
        envelope["checks"]["core_run"] = "PASS"
        envelope["incident_id"] = run.get("incident_id")
        envelope["run_status"] = run.get("status")
        if not isinstance(envelope["incident_id"], str) or not envelope["incident_id"]:
            envelope["reason_codes"].append("INCIDENT_CORRELATION_MISSING")
        if envelope["run_status"] == "BLOCKED":
            envelope["reason_codes"].append("POLICY_BLOCKED_NO_EXECUTION")
    except (HTTPError, URLError, TimeoutError, OSError, ValueError) as exc:
        envelope["checks"]["core_run"] = "HOLD"
        envelope["reason_codes"].append("CORE_RUN_READ_FAILED")
        envelope["error_type"] = type(exc).__name__
        return envelope
    try:
        evidence = _get_json(base_url, "/api/runs/" + rid + "/evidence", token, timeout)
        if not isinstance(evidence, (dict, list)):
            raise ValueError("invalid evidence response")
        envelope["checks"]["evidence_api"] = "PASS"
        envelope["evidence_observed"] = True
    except (HTTPError, URLError, TimeoutError, OSError, ValueError) as exc:
        envelope["checks"]["evidence_api"] = "HOLD"
        envelope["reason_codes"].append("EVIDENCE_READ_FAILED")
        envelope["evidence_error_type"] = type(exc).__name__
    envelope["reason_codes"].append("ITSM_CORRELATION_NOT_VERIFIED")
    return envelope


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--base-url", default="http://127.0.0.1:810")
    parser.add_argument("--timeout", type=float, default=5)
    args = parser.parse_args(argv)
    if args.timeout <= 0:
        parser.error("timeout must be positive")
    try:
        result = collect(args.run_id, args.base_url, timeout=args.timeout)
    except ValueError as exc:
        parser.error(str(exc))
    print(json.dumps(result, sort_keys=True))
    return 0 if result["checks"].get("core_run") == "PASS" and result["checks"].get("evidence_api") == "PASS" else 2


if __name__ == "__main__":
    sys.exit(main())
