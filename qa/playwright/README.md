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

Desktop only: 1440 x 1000. Do not enable screenshots on a runtime with sensitive data. Cosmetic and mobile findings are not release gates.

## Evidence classification

- These tests exercise a real Chromium browser against the URL supplied at execution time.
- A run against localhost is a local runtime observation; a CI run is CI evidence; neither
  proves Debian or production behavior.
- The API checks send no credentials and only assert fail-closed HTTP status. They do not
  fabricate 401/403/503 identities or claim role-specific authorization coverage.
- Routes are discovered from same-origin links and supplemented with known ACME story paths.
  Browser navigation requires HTTP <400 and a matching path; each route is independent.
- No trace/HAR/video is recorded. Console and request data are deliberately not logged.
- Screenshot capture is disabled by default and is not approved for sensitive runtime content.

## Current limits / not covered automatically

- No authenticated operator/tenant personas; no 401 vs 403 differential assertion.
- No backend 503 injection, graph semantic correctness, full workflow identity/digest joins,
  receipt signature verification, or SAN → Twin → Analyst → Critic → Policy → HITL → simulation
  end-to-end execution. These require approved isolated test fixtures/services and explicit
  test identities.
- No LIVE action, external ticket write, deployment, or Debian mutation is performed.

The offline cockpit browser checks verify 17 NOT_RUN/MISSING stages and Twin evidence MISSING, DENY_LIVE_ACTION and NOT_INVOKED. These are not execution receipts.

Use the matrix in the TEAM D report to classify each case PASS / FAIL / BLOCKED / NOT_RUN.


The isolated GitHub Actions workflow is `.github/workflows/team-d-playwright.yml`. It runs against a disposable local FastAPI process with upstream services unreachable; inspect the JUnit artifact before assigning a PASS/FAIL verdict.
