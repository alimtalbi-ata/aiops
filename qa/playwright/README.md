# TEAM D — independent Playwright harness

This harness is additive QA-only content. It does not modify application code, start services,
perform LIVE actions, deploy, or write to Core/GLPI/Temporal. It must target an explicitly
authorized disposable environment or a local read-only portal instance.

## Prerequisites

- Python 3.11+
- The portal already running at the target URL
- Playwright Python and pytest installed

```bash
python -m pip install pytest playwright
python -m playwright install chromium
```

## Run

```bash
AIOPS_QA_BASE_URL=http://127.0.0.1:17777 \
  python -m pytest -c qa/playwright/pytest.ini qa/playwright -q
```

Optional screenshot capture (all editable fields are blanked before capture):

```bash
AIOPS_QA_BASE_URL=http://127.0.0.1:17777 \
AIOPS_QA_CAPTURE=1 AIOPS_QA_ARTIFACT_DIR=artifacts/team-d \
  python -m pytest -c qa/playwright/pytest.ini qa/playwright -q
```

## Evidence classification

- These tests exercise a real Chromium browser against the URL supplied at execution time.
- A run against localhost is a local runtime observation; a CI run is CI evidence; neither
  proves Debian or production behavior.
- The API checks send no credentials and only assert fail-closed HTTP status. They do not
  fabricate 401/403/503 identities or claim role-specific authorization coverage.
- Routes are discovered from same-origin links and supplemented with known ACME story paths.
  A 404/405 is tolerated by the smoke test to expose route inventory drift without hiding it
  in the JUnit report; inspect each response when qualifying a target.
- No trace/HAR/video is recorded. Console and request data are deliberately not logged.
- Screenshots are viewport-only and editable fields are blanked. Review artifacts before sharing;
  dynamic page content can still contain sensitive data and must be manually redacted.

## Current limits / not covered automatically

- No authenticated operator/tenant personas; no 401 vs 403 differential assertion.
- No backend 503 injection, graph semantic correctness, full workflow identity/digest joins,
  receipt signature verification, or SAN → Twin → Analyst → Critic → Policy → HITL → simulation
  end-to-end execution. These require approved isolated test fixtures/services and explicit
  test identities.
- No LIVE action, external ticket write, deployment, or Debian mutation is performed.

Use the matrix in the TEAM D report to classify each case PASS / FAIL / BLOCKED / NOT_RUN.
