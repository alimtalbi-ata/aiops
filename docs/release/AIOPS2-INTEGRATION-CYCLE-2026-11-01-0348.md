# AIOps2 architect integration checkpoint — 2026-11-01 03:48 CET

**RELEASE_STABLE=NO_GO.** Sole Draft candidate [#234](https://github.com/alimtalbi-ata/aiops/pull/234), DEV main base `ae7c3e5102b99a66bd7806d602146f1309a9749d`. No main merge, host or LIVE effects.

## Four scoped ports, not historical merges

| Owner | Source PR / exact HEAD | Candidate selective commit | Paths | Source CI |
|---|---|---|---|---|
| Core P0 | #250 `ae9d17fc0a28d3d2734f4aa6365434b3af6f4653` | `c006d1bee632ff6502b979c27a7f43a9344c12a2` | 6 | Quality 41264746390 3/3; Core 42/42, installed PG16 3/3 |
| Policy/HITL P0 | #251 `dcee21f059d31ce28cc43ba25a00fd1fd707dc48` | `cd35d584783c23898bbe32390128592f55a180f4` | 4 | Quality 41265638520 3/3; Worker 41265638464 2/2, wire 9/9 |
| Portal P0 | #249 `9bfe926d21526196076963ad0264a10603d65f0a` | `0938315d1069bc87cd471f4a66defe14f227c909` | 3 | Quality 41264275862 3/3; ACL 17/17 |
| ACME/Twin P1 | #248 `26e59327d1a9cfa1b93e38cc4227be6005137059` | `d1372c4e9e83369250317ff611456a06a3d6a7fa` | 4 | Quality 41263325980 3/3; ACME 90/90 |

Candidate before this documentation commit `d1372c4e9e83369250317ff611456a06a3d6a7fa`; **the new final HEAD requires independent exact-head CI**. No source CI is inherited. No positive actor+tenant ACL, independent native GLPI User/Profile/Entity authorization, OIDC-to-GLPI mapping, or durable nonce/revocation ledger. Portal dispatch and ALLOW remain disabled. Core REJECT claim/ACK has SQL EXPLAIN, not real populated PG16 concurrency; Worker uses synthetic Core post, not actual Core HTTP. REJECT notification is never approval or executor permission. ACME source-index is synthetic, SLA/OLA, owner, Change and observed impact remain UNKNOWN.

## Gates, dependencies and rollback

D0 new candidate pending; D1 combined disposable ITIL path NOT_QUALIFIED; D2 browser/API same-SHA NOT_QUALIFIED; D3 semantic kit install/upgrade/rollback NO_GO; D4 client sign-off NOT_ATTESTED. #196 benchmark FAIL; tokens provider-reported, cost UNKNOWN.

WIP P0 max 3: Core independently attested actor rights and actual PG16 claim/ACK lease tests; Portal Core signed wire contract without enabling dispatch; Policy same-SHA Core HTTP+PG16+Temporal disposable REJECT integration. ACME P1 preserve pinned Twin provenance and UNKNOWN abstention. Exclusive owner paths; architect owns shared CI and candidate.

Automation A: SRV-DEB-05 cron minute UNATTESTED, host heartbeat/last/next UNKNOWN. B: GitHub Quality schedule 02:23 UTC configured; no schedule-triggered success attested. C: 5/5 ChatGPT hourly schedules enabled, 5/5 next_run_time=null, NEXT_UNKNOWN. D: ACME/Chromium/PG16/Temporal lab disposable only, not runtime validation.

Revert documentation then ACME #248, Portal #249, Worker #251, Core #250 in reverse selective commit order. Dispose of ephemeral data only; no persistent downgrade, no main reset, no real GLPI write, no SSH/sudo or LIVE.
