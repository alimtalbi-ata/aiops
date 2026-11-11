# AIOPS2 — Run rendering atomicity differential (2026-11-11 19:12 CET)

Scope: source-only, branch-only; no host, Docker, tenant ACL, HITL or deployment changes.

## Evidence and differential
- main `app/portal/portal_bootstrap_client.js` blob `ac58f73c725f5e088081bffed4478ea18585ef5c` validates `run_id` as nonempty string but does not type-check `mode`, `status`, `overall_confidence`, `scenario_id`.
- `show()` replaces table rows, then appends each row, coercing every field with `String(run[field] ?? "UNKNOWN")`. A JSON object with a `toString` property that is not callable can make `String(object)` throw a TypeError. The `load()` catch updates the global result to UNKNOWN, but earlier rows may remain visible. This is a source-derived hypothesis, NOT a demonstrated runtime regression.
- Existing source accepts 100 Runs, renders first 15. No deployed v28/V145/candidate image SHA or authenticated HTTP comparison was available.

| Capability | Current source | Candidate acceptance | Active v28/V145 |
| --- | --- | --- | --- |
| Runs malformed field | Only run_id checked; field coercion in rendering | Reject or safely render malformed field, without partial stale table | UNKNOWN |
| Runs truncation | 100 accepted, first 15 displayed | Explicitly disclose truncation and authorized access | UNKNOWN |
| Dashboard/Core/Twin | Qualified ACL envelope required | No relaxation; invalid envelope fail closed | UNKNOWN |
| NOC/GLPI/Copilot/Evidence | Not exercised | Independent provenance and tenant/HITL checks | UNKNOWN |
| Navigation | Not exercised | Routes and consent preserved | UNKNOWN |

## Negative recipe A-019 (NOT EXECUTED)
1. In an isolated DOM harness, mock `fetch("/api/portal/bootstrap")` returning HTTP 200 and a valid `aiops.portal.readmodels.v1` envelope with `tenant_acl_qualified=true`, `actor_identity_server_derived=true`, `runtime_authenticated=false`, `live_remediation_authorized=false`, provenance `UNATTESTED_UPSTREAM_API_READ`, states `dashboard=UNKNOWN`, `twin=UNKNOWN`, `runs=READABLE_UNVERIFIED`; dashboard and twin null.
2. Include two Runs: first normal; second with `run_id="R-2"`, `status={"toString":"not-callable","valueOf":"not-callable"}` (JSON-safe), and other fields normal. Run with valid token in the isolated harness.
3. Assert either (a) entire Runs table fails closed with a visible error and **no prior partial rows**, or (b) the malformed field is rendered as an explicitly unverified, inert placeholder while both rows remain complete. A global UNKNOWN banner alongside a partially populated table is a FAIL.
4. Repeat with a forged tenant ACL flag: assert zero Runs rendered, no second upstream call, no LIVE or remediation badge. Repeat after clear while response JSON is pending: stale response must not repopulate the DOM.
5. Separately test a valid 17-Run envelope with critical failure in position 16: flag truncation and provide tenant-authorized access to the complete set, or mark acceptance FAIL.

## Evidence required for acceptance
Record fixture hash, source and candidate SHAs, Node/browser version, test command and exit code, CI run URL and conclusion, DOM snapshot and timestamp. CI green for docs alone is not execution of A-019. For active/candidate comparison, collect authenticated read-only route response and image digest separately from CI; E2E remains UNVERIFIED.

## Rollback
Close Draft PR or revert only this branch's documentation commits. No main, merge, deployment, Debian, Docker, cron, secrets, PostgreSQL/GLPI, other stacks, or ACL/HITL changes.

## Incident #557
Operator confirmed Docker rootless under aiops UID 1001 with 87 containers/210 images. Rootful sudo docker zero result is a different daemon; do not investigate lost storage or reconstruct. Host freshness is not reverified in this audit.
