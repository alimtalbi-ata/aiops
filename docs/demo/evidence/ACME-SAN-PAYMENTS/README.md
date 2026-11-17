# ACME SAN → Payments — Screenshot evidence pack

**Status: NOT_TESTED / NOT_IMPLEMENTED.** This directory does **not** contain browser screenshots, a verified deployed SHA, or a runtime receipt. No `GO_RUNTIME` or LIVE claim is made.

## Proposed scenes

| ID | Scene | Required |
|---|---|---|
| 01 | NOC overview with SIMULATION watermark | Yes |
| 02 | Signals and correlation | Yes |
| 03 | Twin SAN→storage→Payments path | Yes |
| 04 | Analyst vs Critic | Yes |
| 05 | Policy / simulated HITL | Yes |
| 06 | SIM-GLPI ticket and worker_no_effect receipt | Yes |
| 07 | 17-stage timeline and proof export | Yes |
| 08 | Readiness verdict | Optional |

## Operator instructions (isolated sandbox only)

1. Review real Portal routes and selectors. Replace `NOT_IMPLEMENTED` in `scripts/demo/scenes.yaml` **only when confirmed**. Do not add fake UI or fake PASS.
2. Run only against a local, isolated ACME-TEST sandbox. Review the page for credentials, customer data, IPs, and sensitive incident fields **before publishing any PNG**.
3. Install demo-only dependencies in an isolated environment: `python -m pip install -r scripts/demo/requirements-demo.txt`; `python -m playwright install chromium`. Provisioning can require network access.
4. Set `DEPLOYED_SHA` to the **actual deployed 40-character Git SHA**, not merely the branch HEAD. Set `PORTAL_URL` to a reviewed local sandbox URL. Optionally set `ACME_RUN_ID`.
5. Run `python scripts/demo/capture_acme_screenshots.py`. Exit 0 means seven mandatory scenes captured with assertions; optional scene 08 may be NOT_IMPLEMENTED.
6. Independently verify five sandbox capabilities, E2E receipt and `GO_SIMULATION_ONLY` via the readiness gate. Browser captures alone are not readiness evidence.
7. Inspect every screenshot manually and sanitize any sensitive data **before committing**. Never commit cookies, session storage, auth headers, internal hostnames, secrets, or real tenant data.

The script uses read-only navigation and no login automation, and writes `meta.json` with PASS/FAIL per scene. A missing route, selector, simulation watermark or deployed SHA fails closed. `meta.json` records a claimed SHA; it **does not prove** that SHA was executed. Runtime attestation remains a separate blocker in [#804](https://github.com/alimtalbi-ata/aiops/issues/804).

No screenshot or runtime receipt is committed by this draft PR.
