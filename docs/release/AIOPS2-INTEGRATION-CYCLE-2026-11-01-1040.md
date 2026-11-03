# ADR — 2026-11-01 10:40 CET AIOps2 focused four-team integration

**Status:** ACCEPTED for DEV-only candidate composition, **NOT** accepted as release approval. Sole [Draft #234](https://github.com/alimtalbi-ata/aiops/pull/234), base main `ae7c3e5102b99a66bd7806d602146f1309a9749d`, previous HEAD `5d06311c6bc53d6d60c54483f485acfa5df8eba8`, product port `c7c05aa70d49e45b65b8db5f287723ab88bbe6bf`. Four source Drafts #276/#277/#278/#279 remain unmerged.

## Decision and dependency order

Selectively import 14 exact Git blobs, **not** divergent PR histories. Order of contract qualification: Core independently authenticated tenant/actor/Incident/Run/source-event readback → ACME seven immutable source event hash reconciliation → Portal human GLPI native permission + signed Core response → Policy/HITL REJECT-only durable notification. The current source lots are negative/shape qualification, not a positive operator journey. ACME has no real receipt; Portal valid offline RSA ALLOW is intentionally rejected; Core pinned HTTPS readback is only a necessary preflight and remains UNKNOWN; Worker DEAD is SQL-injected in disposable PG16 and no runtime dead-letter API exists. No parallel GLPI authority or alternate ledger.

## Exact source provenance and tests

- ACME #276 `d54be9fe6babe3d60568363d5515e59e6487cda3`: Quality [41291051671](https://github.com/alimtalbi-ata/aiops/actions/runs/41291051671) 3/3, 160/160 targeted. Three paths.
- Portal #277 `34115ff47009f7085b3223f90c9feeb9abc3b336`: Quality [41292392857](https://github.com/alimtalbi-ata/aiops/actions/runs/41292392857) 3/3, Chromium 19/19, consumer 22/22, OIDC 12/12. Two paths.
- Core #278 `f8ce7dc7cd8d24decef19847de8720939e6bb745`: Quality [41292933631](https://github.com/alimtalbi-ata/aiops/actions/runs/41292933631) 3/3, Core 91/91, xref 20/20, installed PG16 14/14. Six paths.
- Policy #279 `6c4a8bb03534088355864c1ff41b39e173c2be6a`: Quality [41293262077](https://github.com/alimtalbi-ata/aiops/actions/runs/41293262077) 3/3, combined [41293262009](https://github.com/alimtalbi-ata/aiops/actions/runs/41293262009) 1/1 with 8/8 + DR 5/5. Three paths.

**Candidate CI after port:** PENDING; source CI is not portable to new SHA. No changes to migration files; 001/004/009→013 and native PG16 16.15 restore must be requalified. No permission to merge a Draft even if green.

## Threat boundaries and acceptance

Core canonical Incident/Run, GLPI authoritative ITSM/CMDB, source provenance and freshness, OIDC human identity, GLPI native User/Profile/Entity, tenant ACL and nonce/JTI immutable 013 must all be independently attested before any ALLOW. AI Analyst/Critic advisory only; Policy deterministic; Temporal signal notification-only; no LIVE. Require T2 disposable end-to-end with exact IDs/evidence, D2 browser/API same SHA, D3 cumulative install/upgrade/rollback manifests and checksum verification, D4 explicit human signoff. Until then **RELEASE_STABLE=NO_GO**.

## Revert

On candidate only, revert this ADR/docs commit then `c7c05aa70d49e45b65b8db5f287723ab88bbe6bf` with new commits, rerun exact-head CI. Never force-push, reset main, DROP/DELETE/UPDATE 013 audit or touch external GLPI/IdP. Main unchanged. No production, host or customer validation claimed.
