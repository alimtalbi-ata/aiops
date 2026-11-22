"""Contract for a CI-local Chromium smoke result; never runtime attestation."""
import json
from pathlib import Path

def qualify_local_browser_run(*, source_sha: str, job_passed: bool) -> dict:
    if not isinstance(source_sha, str) or len(source_sha) != 40 or any(c not in "0123456789abcdef" for c in source_sha):
        raise ValueError("invalid source sha")
    if type(job_passed) is not bool or not job_passed:
        raise ValueError("browser smoke did not pass")
    return {
        "schema": "aiops.acme-isolated-browser-receipt.v1",
        "source_sha": source_sha,
        "status": "PASS_CI_LOOPBACK_BROWSER_ONLY",
        "browser": "CHROMIUM",
        "viewports": [375, 1440],
        "navigation": ["/demo-studio", "/acme-workbench"],
        "external_requests": "BLOCKED_BY_BROWSER_TEST",
        "upstream_services": "DISABLED_BY_TEST_APP",
        "deployed_sha_attested": False,
        "runtime_e2e_verified": False,
        "viewer_acl_verified": False,
        "remediation_effect_verified": False,
        "learning_verified": False,
        "autonomous_execution_allowed": False,
    }


if __name__ == "__main__":
    import os
    result = qualify_local_browser_run(source_sha=os.environ["GITHUB_SHA"], job_passed=True)
    output = Path(os.environ["ACME_BROWSER_RECEIPT_PATH"])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
