#!/usr/bin/env python3
"""Offline, non-mutating Portal candidate preflight. Synthetic != host qualification."""
import argparse
import json
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[3]
GATES = [
    ("history-matrix", ["python3", "scripts/fs/tests/test_fs1113_history_matrix_supersession.py"]),
    ("history-empty-a11y", ["python3", "scripts/fs/tests/test_fs1113_history_empty_accessibility.py"]),
    ("history-accessible-context", ["python3", "scripts/fs/tests/test_fs1113_history_accessible_context.py"]),
    ("history-aria-busy", ["python3", "scripts/fs/tests/test_fs1113_history_aria_busy.py"]),
    ("history-contract", ["python3", "scripts/fs/tests/test_fs1113_history_contract_failclosed.py"]),
    ("history-auth", ["python3", "scripts/fs/tests/test_fs1113_history_auth_denial.py"]),
    ("readonly-and-components", ["node", "--test",
        "app/portal/components/operational_state.test.mjs",
        "app/portal/components/evidence_filter.test.mjs",
        "tests/test_portal_consolidated_readonly_contract.mjs",
        "tests/test_portal_navigation_supersession.mjs"]),
    ("http-404-405", ["python3", "-m", "pytest", "-q",
        "tests/test_portal_error_response_security_20261110.py",
        "tests/test_portal_method_error_security_20261110.py"]),
]
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", help="emit machine-readable summary")
    args = parser.parse_args()
    results = []
    if not GATES:
        results.append(dict(gate="manifest", status="FAIL", reason="no gates configured"))
    seen = set()
    for entry in GATES:
        if (not isinstance(entry, (tuple, list)) or len(entry) != 2
                or not isinstance(entry[0], str) or not entry[0]
                or not isinstance(entry[1], (tuple, list)) or not entry[1]
                or not all(isinstance(arg, str) and arg for arg in entry[1])):
            results.append(dict(gate="manifest", status="FAIL", reason="invalid gate definition"))
            continue
        name, command = entry
        if name in seen:
            results.append(dict(gate=name, status="FAIL", reason="duplicate gate name"))
            continue
        seen.add(name)
        missing = [path for path in command[1:] if path.endswith((".py", ".mjs")) and not (ROOT / path).is_file()]
        executable = shutil.which(command[0])
        if missing or not executable:
            results.append(dict(gate=name, status="NOT_EXECUTED", reason="missing files or executable", missing=missing, executable=command[0]))
            continue
        try:
            run = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=120)
            # Do not persist subprocess output: test logs may contain tokens, URLs or headers.
            # Gate name, status and exit code are sufficient for this offline receipt.
            results.append(dict(gate=name, status="PASS" if run.returncode == 0 else "FAIL", exit_code=run.returncode))
        except subprocess.TimeoutExpired:
            results.append(dict(gate=name, status="FAIL", reason="timeout 120s"))
        except OSError:
            # Runner failures must remain fail-closed and never expose exception text
            # (which can contain environment paths or subprocess diagnostics).
            results.append(dict(gate=name, status="FAIL", reason="runner unavailable"))
    summary = dict(kind="SYNTHETIC_OFFLINE_ONLY", host="NOT_VERIFIED", debian="NOT_VERIFIED",
                   chromium="NOT_VERIFIED", live="UNKNOWN", gates=results)
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        for result in results:
            print(result["gate"] + ": " + result["status"])
        print("Chromium/CSP/responsive/tenant ACL/Policy-HITL/host E2E: NOT_VERIFIED")
    return 0 if all(x["status"] == "PASS" for x in results) else 1

if __name__ == "__main__":
    sys.exit(main())
