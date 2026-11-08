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
