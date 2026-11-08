# AIOps2 — Inventaire transversal de réutilisation (premier passage)

**Date:** 2026-11-08. **Statut:** PARTIAL / DISCOVERY, NOT a complete inventory or release approval.
**Repository:** alimtalbi-ata/aiops. **Audit branch:** audit/preserve-debian-48h-20261108.

## Rules
- Search main, stable, component branches, historical PRs, and v1/V145 reuse material before declaring a capability missing or implementing a replacement.
- A branch/PR title proves existence of a candidate, **not** merge, current compatibility, production deployment or E2E success.
- Verify exact head SHA, diff, source dependency, CI on that SHA, schema/migrations, and Docker image provenance before reusing.
- No GLPI ticket writes, direct PG backfill, unapproved Debian deploy, LIVE action or auto-merge.

## Discovered source candidates (non-exhaustive)

| Area | Source references | What exists / evidence | Qualification gap / action |
| --- | --- | --- | --- |
| FS1250/FS147 ITSM reconciliation | [PR #454](https://github.com/alimtalbi-ata/aiops/pull/454), branch core/fs147-fs1250-reconcile-20261108 | Open Draft. Adds app/core/itsm_reconcile_contract.py and Core admission/lineage gates, with four test files; PR body reports 13 synthetic tests for initial classifier. | No GLPI readback, durable xref repair, Debian qualification or deploy. Candidate only. |
| Core tenant-scoped ITSM xref read | [#205](https://github.com/alimtalbi-ata/aiops/pull/205), [#229](https://github.com/alimtalbi-ata/aiops/pull/229), [#233](https://github.com/alimtalbi-ata/aiops/pull/233), [#242](https://github.com/alimtalbi-ata/aiops/pull/242) | Existing Core read contract and progressively stronger ownership and GLPI Ticket/Entity/CI readback fences. #242 reports exact-head CI success with disposable PG16 and mocked GLPI. | Draft candidate chain; independent real GLPI attestation and deployed source match NOT_VERIFIED. Compare source and migration chain before selective reuse. |
| Migration provenance | [#212](https://github.com/alimtalbi-ata/aiops/pull/212), #229/#233 | ITSM xref migration renumbered to 012 to avoid 009 collision. | Audit branch only contains migrations 000–008; Debian has glpi_ticket_links and itsm_xref_events. Never apply migration without matching installed schema history. |
| FS364 atomic ticket correlation | [#440](https://github.com/alimtalbi-ata/aiops/pull/440) | Draft SQLite atomic/idempotent reference binding for existing GLPI #147. | Not a PostgreSQL production implementation; no GLPI create or live source readback. |
| GLPI actor/Portal rights | [#192](https://github.com/alimtalbi-ata/aiops/pull/192), [#241](https://github.com/alimtalbi-ata/aiops/pull/241), [#258](https://github.com/alimtalbi-ata/aiops/pull/258), [#285](https://github.com/alimtalbi-ata/aiops/pull/285), [#315](https://github.com/alimtalbi-ata/aiops/pull/315), [#327](https://github.com/alimtalbi-ata/aiops/pull/327), [#330](https://github.com/alimtalbi-ata/aiops/pull/330) | Multiple prior actor/tenant ACL, OIDC, GLPI native ownership and 403 fail-closed proposals. | Review diffs/merges; don't claim absent because audit Portal has read-only shell. |
| GLPI native integration and Copilot | [#193](https://github.com/alimtalbi-ata/aiops/pull/193), [#359](https://github.com/alimtalbi-ata/aiops/pull/359), [#357](https://github.com/alimtalbi-ata/aiops/pull/357), [#444](https://github.com/alimtalbi-ata/aiops/pull/444); branches feat/glpi-ai-ticket-enrichment-e2e, feat/glpi-hitl-proposal-fastpath, feat/p1-glpi-real-http-ci-20261028 | Multiple existing feature branches. Audit integration/glpi_copilot_bridge.py imports portal.glpi_client not found in the audit tree; this does **not** prove missing in other branches/images. | Find actual GLPIClient source and deployed writer before implementation. |
| Temporal/Worker/HITL | [#194](https://github.com/alimtalbi-ata/aiops/pull/194), [#446](https://github.com/alimtalbi-ata/aiops/pull/446), [#450](https://github.com/alimtalbi-ata/aiops/pull/450) | Existing source candidates for worker execution guard and Core action-bound HITL. | No inference of safe LIVE or real FS1250 execution; blocked run has NOT_APPLICABLE worker action. |

## Live Debian observations to preserve
- SRV-DEB-05: RUN-8CA56A39E58944F1, INC-FS1250-AUTOGLPI-625916362ACD42C9; ticket #201 observed in GLPI UI, **not authenticated readback**.
- Core policy BLOCKED; Critic denial outbox reconciled. 44 historical CONFIRMED links, no matching FS1250 link, itsm_xref_events empty. E2E ITSM linkage remains HOLD.
- GLPI API is already functional. Never rebuild or replace it merely because audit Core/Worker OpenAPI exposes no GLPI endpoint.
- Live images: aiops2-core:fs1212-integrated-candidate, aiops2-worker:fs-demo-candidate-20261105, glpi/glpi:11.0.9; source-to-image provenance not yet mapped.

## Next discovery passes
1. Enumerate **all** GitHub branches and PRs (this first pass sampled branch pages and topic searches only), group by component and capability; capture exact SHA, merge state, files, tests, CI, dependencies and conflicts.
2. Find actual GLPI API client and ticket writer in source branches and n8n; compare FS1130 confirmed writer to FS1250 path.
3. Compare live Docker image IDs/digests and installed migration provenance with source candidates, read-only.
4. Selectively reuse proven code, test duplicate suppression and blocked Policy safety; deploy only with explicit operator approval.

## Session handoff
ChatGPT owns architecture/evidence review; Codex owns code investigation/patch/test; GitHub is shared durable continuity; Debian is runtime truth. Read docs/PROJECT-CONTINUITY.md, docs/COMPONENT-CATALOG-AND-REUSE.md and this file at session start. Do not treat this preliminary index as complete.

## Discovery pass 2 — 2026-11-08 (verified files in other branches)

- GitHub branch listing returned **483 branch names** across five pages (100+100+100+100+83), including `main`, `deploy/aiops2-stable`, and numerous historical integration, Core, Worker and Portal branches. This is branch-name enumeration, **not** full file/PR review. Never equate the 297-file audit tree with the complete project.
- **Actual GLPI REST client found:** `feat/glpi-ai-ticket-enrichment-e2e:app/portal/glpi_client.py`, blob SHA `8cd3cd2381356e23d777dd6c0087ac03bd9b7375`, 149 lines. Implements authenticated server-side GLPI REST client with `GLPI_API_URL`, `GLPI_APP_TOKEN`, `GLPI_USER_TOKEN`. This resolves the earlier mistaken apparent absence of `portal.glpi_client` in the audit branch. **Do not expose credentials; do not assume branch is deployed.**
- **Existing Core ITSM xref code found:** `fix/core-xref-glpi-readback-gate-20261101:app/core/itsm_xref.py`, blob SHA `c59c2a281be351ce61064269dbc65bc4b689d9aa`, 345 lines; read-only tenant-scoped xref with GLPI source readback fences. Associated PR #242; no evidence of live deployment.
- **FS1250 classifier source found:** `core/fs147-fs1250-reconcile-20261108:app/core/itsm_reconcile_contract.py`, blob SHA `49dacf4b11813df1aeab72cc92361ed7e8aed739`, 73 lines; distinguishes MATCHED, EXISTING_UNLINKED, AMBIGUOUS, MISSING, NOT_ELIGIBLE, UNKNOWN, CONFLICT. PR #454 remains Draft and non-mutating.
- Other potentially relevant branches include `fix/fs1250-itsm-identity-audit`, `feat/p1-glpi-real-http-ci-20261028`, `feat/portal-signed-core-glpi-native-contract-20261101-1110`, `feat/portal-sim-glpi-stable-readback-20261102-2105`, `integration/core-xref-migration-012-20261031`, `release/acme-core-worker-ticket-20261103`. Not yet inspected; names alone prove no functionality.

**Updated decision:** GLPI client and xref read contracts are **ALREADY DEVELOPED in other GitHub branches**. Before writing any new code, compare their exact dependencies and historical branches with `deploy/aiops2-stable` and the running Debian images. No new GLPI API implementation is justified by the audit-branch absence.

## Discovery pass 3 — GLPI API source behavior (2026-11-08)

**Important correction:** the already-developed `feat/glpi-ai-ticket-enrichment-e2e:app/portal/glpi_client.py` (blob `8cd3cd2381356e23d777dd6c0087ac03bd9b7375`) is **not only a read client**. It contains `get_ticket` (line 82), `search_tickets` (87), `create_ticket` (102, native POST Ticket), `update_ticket` (121, native PUT Ticket), and `find_ticket_for_run` (130). This is a **write-capable historical implementation**. Presence in a feature branch does not prove it is deployed, invoked, authorized or safe for FS1250. Any reuse must disable/guard ticket creation and update for the FS1250 reconciliation path to prevent duplicates.

The existing `fix/core-xref-glpi-readback-gate-20261101:app/core/itsm_xref.py` (blob `c59c2a281be351ce61064269dbc65bc4b689d9aa`) is **read-only**: `_glpi_readback` at line 93 performs authenticated source verification including Ticket and Item_Ticket; `GET /api/tenants/{tenant_id}/itsm/glpi/{instance_id}/tickets/{ticket_id}/xref` at line 293; `_evaluate` at line 223 requires scoped signed source/ownership. It does not write the missing FS1250 xref. Compare with actual deployed schema and client configuration before selective port.

The `core/fs147-fs1250-reconcile-20261108:app/core/itsm_reconcile_contract.py` (blob `49dacf4b11813df1aeab72cc92361ed7e8aed739`) is a pure classifier (`classify` line 34), not a writer. **Do not connect its EXISTING_UNLINKED outcome directly to a mutation.**

**Next targeted trace:** find callers of `GLPIClient.create_ticket`, `update_ticket`, `find_ticket_for_run`, existing outbox/event consumer and deployed FS1130 producer. Compare with PR #455 read-only diagnostic and #454 classifier. No source changes, GLPI writes or Debian access performed in this pass.
