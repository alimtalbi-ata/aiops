# ADR — AIOps2 four-owner selective integration, 2026-11-01 06:45 Europe/Paris

Decision: keep sole Draft [#234](https://github.com/alimtalbi-ata/aiops/pull/234) based on DEV main `ae7c3e5102b99a66bd7806d602146f1309a9749d`. Port 18 source-reviewed paths from Draft #260/#261/#262/#263 using exact Git blob SHAs, in architect commit `44f98ab51a21546efa837bb6571afa08b1e7476f`, not their divergent branch histories. Source exact-head Quality 3/3 each and Policy combined 1/1, integrated CI must run on the NEW HEAD. No main merge, no LIVE.

## Contracts and boundaries

1. ACME/Twin #260: seven events, local synthetic test partitions, pinned SAN→Payments candidate impact. Not real tenant auth, no Incident/GLPI/Evidence write or model inference; 15-stage ITIL runtime remains NOT_EXECUTED.
2. Portal #261: real headless Chromium and disposable HTTPS Portal, negative 401/503 actor/tenant/Run/ticket/entity, no Core fetch, no ALLOW. Legacy viewer gate remains separate from OIDC identity.
3. Core #262: native human GLPI rights preflight and PostgreSQL 013 durable issuer/JTI/nonce consumption. Every outcome UNKNOWN or 503 UNKNOWN, even successful first consume. Keep audit ledger immutable. Synthetic IdP/GLPI mocks are not independent authorization.
4. Policy/HITL #263: independent disposable Core TCP service, real Temporal dev-server restart with SQLite persistence, gateway-close after Core commits ACK, REJECT-only signals. Not physical packet loss, no APPROVE or effect.

Dependencies: Core independently authenticated GLPI human User/Profile/Entity/Ticket rights + IdP mapping → actor-resource signed response and tenant fence → Portal exact read permission → business E2E; REJECT Worker and synthetic ACME are separate subpaths. GLPI is authoritative for ITSM/CMDB when qualified; no shadow CMDB. Migration 001→004→009→010→011→012→013, never drop 013 audit on code rollback.

Gates D0 integrated CI PENDING, D1 full ITIL NOT_QUALIFIED, D2 full same-SHA browser/API NOT_QUALIFIED, D3 kit NO_GO, D4 signoff NOT_ATTESTED. Benchmark #196 FAIL and cost UNKNOWN. SOURCE_REVIEWED != CI_PASS != INTEGRATION_PASS != RUNTIME_OBSERVED. Rollback via new revert commit of `44f98ab5`, disposable DB teardown only, no main reset/force push. No real GLPI writes, Debian SSH/sudo/cron/runner, executor activation or LIVE.
