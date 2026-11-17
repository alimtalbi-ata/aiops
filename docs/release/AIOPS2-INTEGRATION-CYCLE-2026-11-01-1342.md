# AIOps2 integration cycle — 2026-11-01 13:42 CET

## Decision
Sole integration Draft #234, main ae7c3e5102b99a66bd7806d602146f1309a9749d, prior candidate bbe95d9894df13ab910c2b99ccb3d09ec32aa678; selective 13 Git blobs from source Drafts #289/#290/#291/#292, no source-history merge, no schema/migration. New candidate exact-head CI PENDING; **RELEASE_STABLE=NO_GO**. All four source PRs remain Draft and source CI green; no promotion.

## Team control
| Team / owner | PR branch HEAD / base | Scope and source CI | Blocker / next |
|---|---|---|---|
| ACME/Twin P1 | #289 feat/acme-core-seven-domain-receipt-20261101-1300 d55049cfc5627db5006667f05d459762002f1012 / bbe95d9894df13ab910c2b99ccb3d09ec32aa678 | 4 files, Quality 41304723889 3/3, 193/193 | Core full-event mapping UNKNOWN; coordinate independent canonical bytes |
| Portal/GLPI P0 | #290 feat/portal-authority-negative-receipts-20261101-1308 b929bd8b0058c7f2e5a023631de14eae4db15aeb / bbe95d9894df13ab910c2b99ccb3d09ec32aa678 | 2 files, Quality 41305414476 3/3, 51/51 | native GLPI human rights/IdP and durable signer/replay NOT_ATTESTED; remain 503/401 |
| Core/NOC P0 | #291 fix/core-canonical-seven-receipts-20261101-1323 5514ce77728bfd7bf0ce6a1ccf3a6b9a2a9c946d / bbe95d9894df13ab910c2b99ccb3d09ec32aa678 | 4 files, PG16 41306396835 12/12 + Quality 41306396816 3/3 | source receipt unsigned UNKNOWN; next Core-owned atomic audited DEAD API contract |
| Policy/HITL P0 | #292 feat/p0-worker-dead-negative-receipt-20261101-1329 df978fc28d0d776e364d83dea587a8d82683f722 / bbe95d9894df13ab910c2b99ccb3d09ec32aa678 | 3 files, PG16/Temporal 41306864067 10/10 + DR 5/5 + Quality 41306864394 3/3 | runtime LEASED attempts=8 not DEAD; next verify Core terminal transition after Core implements |

## Source evidence and safety
ACME 7 ordered IDs and 3 distinct hash domains; 15 ITIL stages and 6 checkpoints NOT_EXECUTED. Portal negative receipts 503 UNKNOWN/401 revoked, no positive GLPI. Core read-only PG16/TLS source receipts nonportable, actor and ticket UNKNOWN, migration 013 audit immutable. Worker two REJECT outbox rows remain LEASED attempts=8 after two persisted disposable Temporal restarts, no signals, APPROVE, effects, or LIVE. No source authority duplication.

## Host evidence
SRV-DEB-05 GitHub reporter `ops/debian-runtime-reports:ops/debian-reports/SRV-DEB-05/latest.json` collected 2026-11-01T12:39:01.503953+00:00: 61 total; 53 running/8 exited; 22 healthy/38 no-healthcheck/1 unhealthy. Active rebuild Portal/Core running healthy; old rollback portal exited/unhealthy, not an active outage. Cron/SSH commands NOT_TESTED from this run. #286 duplicate publisher HOLD.

## Gates / rollback
SOURCE_REVIEWED=13 exact blobs, CI_PASS=source exact-head, INTEGRATION_PASS=PENDING candidate exact-head, RUNTIME_OBSERVED=CI disposable + GitHub-published host inventory only, NOT_VERIFIED=real GLPI IdP human rights, Core DEAD, ACME full-event equivalence, complete ITIL E2E, release kit install/upgrade/rollback. No merge main, no deploy/aiops2-stable push, no host/SSH/sudo, no Docker/volume or real GLPI mutation. Revert only the selective integration commit, re-run all new exact-head CI; preserve immutable migration 013 rows and main history. Final new SHA and CI links to be journaled in #186 after GitHub Actions.
