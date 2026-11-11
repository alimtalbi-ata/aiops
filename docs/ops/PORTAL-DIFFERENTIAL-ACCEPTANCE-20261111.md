# Portal AIOPS2 — recette différentielle avant/après (2026-11-11 00:12 UTC)

Scope: **read-only qualification**, not reconstruction, deployment, or ACL bypass. Source base: PR #560 commit `c550fae09999a44790ab3e4477b442a357156221`. This document is a test protocol, **not an execution receipt**.

## Provenance gate (mandatory before every comparison)

For each target, record UTC collection time, hostname, Docker context/user, container ID, immutable image digest, source commit/labels if available, request URL, identity class (anonymous vs approved tenant/actor), status, response headers, redacted body hash, and evidence artifact path. Never infer source SHA from image tag. For Debian use only authorized rootless read-only receipts (aiops UID 1001; socket /run/user/1001/docker.sock), **not** `sudo docker`. If receipt age exceeds 180 seconds mark STALE; missing HTTP evidence = UNKNOWN. No new SSH or runtime access is authorized by this protocol.

As of the receipt `ops/debian-runtime-reports:ops/debian-reports/SRV-DEB-05/latest.json`, collected `2026-11-11T00:11:01.588084Z`, the active portal is reported running on `sha256:a1f3adcf1e1189600d3167f6d5f3970a89deefe99338b19a8f089da08502916b` (no healthcheck). It does **not** prove HTTP behavior or commit provenance. Prior rootful 0/0 inventory was a false diagnostic (#557). Candidate 17778 has no HTTP receipt here.

## Differential matrix and acceptance criteria

| Capability / route | Before (v28/V145 or fs rollback) | Active 7777 | Candidate 17778 | Contract / negative case | Risk, suspected cause (hypothesis only), priority | Restoration strategy |
| --- | --- | --- | --- | --- | --- | --- |
| Shell `GET /` and navigation | UNKNOWN | UNKNOWN | UNKNOWN | 200 for public shell; discover Runs/Twin/NOC/Copilot/ITSM; no anonymous Core/Twin calls; UNKNOWN placeholders, no-store | Missing anchors after shell refactor; P1 | Restore only missing navigation markup from reviewed source; keep ACL checks |
| Dashboard `/api/portal/bootstrap` | UNKNOWN | UNKNOWN | UNKNOWN | Unqualified tenant/actor must remain 503 + UNKNOWN; no upstream reads | Accidental authorization widening; P0 | Preserve fail-closed and qualify identity before enabling |
| Component navigation `/api/portal/components` | UNKNOWN | UNKNOWN | UNKNOWN | Unqualified actor 503 + UNKNOWN; no tenant leakage | Shared viewer token mistaken for tenant grant; P0 | Server-side tenant/actor qualification only |
| Core / Twin / Runs UI | UNKNOWN | UNKNOWN | UNKNOWN | Qualified read-only actor: inspect run/incident correlation; missing data stays UNKNOWN; no synthetic success | Contract drift or incomplete source/image mapping; P1 | Contract adapter after evidence of drift, not blanket route enable |
| Copilot `POST /api/copilot` | UNKNOWN | UNKNOWN | UNKNOWN | Unqualified tenant must be denied before upstream call; no secret/body logging | Permission bypass; P0 | Retain ACL guard; independently review allowed actor |
| NOC / GLPI / ITSM | UNKNOWN | UNKNOWN | UNKNOWN | Navigation discoverable; no creation of GLPI ticket; existing ticket references read-only | Hidden navigation or xref ambiguity; P1 | Restore discovery only; do not write ITSM |
| Evidence and visualization | UNKNOWN | UNKNOWN | UNKNOWN | Empty/timeout/denied are not success; CSP and same-origin history; 1h/6h/24h selection does not duplicate series | Stale fetch race / misleading empty state; P1 | Reuse FS1113 request cancellation, #551 accessible empty-state; require CI and HTTP receipt |

Historical images to inventory **read-only**: `aiops2-portal:fs1073-csp-candidate`, `fs1051-visual-candidate`, `fs621-explorers-candidate`; historical sources v28/V145 require immutable source SHAs. Never equate these tags with the running portal. Current receipt lists fs1073/fs1051/fs621 rollback containers exited; this is not a route comparison.

## Reproducible qualification

1. Record provenance per target; if source SHA or HTTP identity is missing, keep corresponding cell UNKNOWN.
2. Run `pytest -q tests/test_portal_shell_capability_contract_20261111.py` at the exact candidate SHA and attach stdout, exit code and CI run URL. This only tests candidate source.
3. For each authorized target, collect `GET /` and read-only `GET /api/portal/bootstrap`, `GET /api/portal/components` with *approved* actor context, plus anonymous negative requests. Do not generate POST side effects. Compare redacted status, headers, anchor presence, and semantic states; do not copy tokens or personal data.
4. Run browser test for quick 1h→6h→24h→1h history switches: legend count must match distinct API series (historical FS1109 reference: five series), no stale series retained. Do not claim five series on an unverified current API.
5. Record each delta as REGRESSION, INTENTIONAL_SECURITY_DENIAL, UNKNOWN, or PASS only with both before/after evidence. Any missing identity or data => UNKNOWN/NEEDS_HUMAN. Stop promotion on security widening, false-success state, or unproven rollback.

Rollback of **this documentation-only candidate**: close Draft PR or revert its isolated commit. No runtime rollback is performed or authorized. Handoff: issue #555; canonical handover remains `docs/ops/HANDOVER-AIOPS2-CURRENT.md` on branch `docs/debian-deployment-qualification-plan-20261110` (do not overwrite concurrently).
