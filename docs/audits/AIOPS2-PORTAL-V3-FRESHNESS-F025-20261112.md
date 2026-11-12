# F-025 — Freshness and provenance fail-closed acceptance gate
Date: 2026-11-12 Europe/Paris. Scope: AIOPS2 / Portal V3 only. DOCUMENTED, NOT EXECUTED.

## Differential matrix (no unsupported parity claim)
| Capability | v28/V145 baseline | stable / Debian | Portal V3 candidate | Negative acceptance |
|---|---|---|---|---|
| Dashboard / incidents | UNKNOWN | UNKNOWN | UNKNOWN | stale metrics cannot show LIVE |
| CMDB / service map | UNKNOWN | UNKNOWN | UNKNOWN | cross-tenant node denied |
| NOC | UNKNOWN | UNKNOWN | UNKNOWN | expired incident source UNKNOWN |
| Core / Twin / Runs | UNKNOWN | UNKNOWN | UNKNOWN | asynchronous stale Run ignored; no partial rendering |
| Evidence | UNKNOWN | UNKNOWN | UNKNOWN | missing provenance never VERIFIED |
| Policy / HITL | UNKNOWN | UNKNOWN | UNKNOWN | no implicit approval or LIVE |
| Prometheus / Grafana | UNKNOWN | UNKNOWN | UNKNOWN | CI green cannot assert fresh host metrics |
| GLPI | UNKNOWN | UNKNOWN | UNKNOWN | ticket writes prohibited in read-only journey |
| Copilot ticket / portal | UNKNOWN | UNKNOWN | UNKNOWN | prompt cannot override ACL |
| Navigation / auth | UNKNOWN | UNKNOWN | UNKNOWN | 401/403/404/405 and keyboard routes |
No source-level or runtime comparison of all three versions was performed this cycle; UNKNOWN is intentional.

## New negative protocol F-025 (synthetic, unexecuted)
Given a rootless host observation with collected_at=2026-11-08T12:00:00Z, valid structure, observed Docker count, and source=SRV-DEB-05, when rendered on 2026-11-12, expected host freshness=STALE/UNKNOWN and deployment gate=NO_GO. A GitHub CI check with success at candidate SHA must NOT change host freshness. A report with missing collected_at, future timestamp, failed socket, timeout, truncated inventory, or rootful endpoint MUST be UNKNOWN and not imply lost containers. No raw logs, env, secrets, volume contents, or image names should be exposed.

Positive control: recent observation from UID 1001 and unix:///run/user/1001/docker.sock, with exact host identity, bounded age and complete counts, may be classified FRESH only for host metadata; it is NOT evidence of application E2E or authorization.

Acceptance: assert source identity, capture time, ingestion time, freshness TTL (review-defined), complete counts, UID/context, collector version and SHA, explicit UNKNOWN. No host mutation in test. Test status: NOT_EXECUTED.

## Collector qualification checklist
Review #670 and #673 together before installation: rootless UID=1001; rootless socket; Docker metadata counts and completeness; services/systemd --user; ports; volumes names/counts only; masked logs or UNKNOWN; cron metadata only; flock; timeout; umask 077 / JSON 0600; bounded retention; SHA and UTC timestamp; error status UNKNOWN. Do not enable cron until review. Do not expose raw image tags or sensitive command arguments.

## Release gates
CODE: candidate SHA pinned and reviewed. CI: successful at SAME SHA, required checks complete (cancelled != success). DEBIAN: authenticated host observation, backups and reversible portal-only deployment plan, no rootful inference. E2E: auth/ACL/HITL and smoke checks explicitly executed. Until all gates: NO_GO for deployment.

## Rollback
Documentation-only branch: close Draft PR or revert its commits; no runtime rollback necessary. No main merge, cron installation, SSH, Docker changes, GLPI writes, LIVE or deployment performed.
