# AIOPS2 — Contract acceptance ledger (2026-11-16 13:37 Europe/Paris)

**Scope:** DEV documentation only; exact integration base `91551be28bc1383062669ef48d9c29aff6a83718` (PR #713, DRAFT, mergeable=false). This ledger is a test specification, not an execution certificate. No LIVE or real effects.

## Single P0 backlog (WIP=3, no fourth lane)

| Rank | Owner / candidate SHA | Boundary | Acceptance evidence required | Current verdict |
|---|---|---|---|---|
| 1 Correlation | Core #718 `5f8a3fb00882d7cbfc1ca164ed4bf19173e6d404` | event tenant/source identity → canonical incident/run correlation | exact-head adversarial test receipt, 0 cross-tenant joins, deterministic dedup and conflict→UNKNOWN, source-event provenance | BLOCKED |
| 2 Business Twin | Twin #715 `3da16e9177bf6afbacfd79742b7f910663e95c4d` | canonical incident/service ID → versioned tenant-scoped SAN→storage→Payments graph | fixture proof with graph version, edge authority/source/observed_at/attested, max-age; missing/stale/cross-tenant→UNKNOWN; no causality inferred from correlation | BLOCKED |
| 3 Analyst/Critic/RAG | Policy #716 `2d6b794a2fdd2cb4862197a7c39d9fe03ef708a2`; #720 `f4023ae3571bc4b55025a5243bd1a9bc6c05fb26` | immutable evidence IDs → cited hypotheses → independent Critic → deterministic Policy/HITL | reject fabricated/stale/cross-tenant citations; Critic independence attested outside self-declared model field; missing HITL approval→DENY_LIVE, zero external effects | BLOCKED |

NOC #719 is a downstream **read-only candidate**, not a fourth P0. ITSM is downstream and must not create tickets during these gates.

## Contract-level negative acceptance matrix

1. **Correlation:** inject two tenants with identical service/event fingerprints; output MUST NOT share incident/run identity. Replay same source-event ID twice; count MUST remain one logical event, with an auditable receipt. Conflicting or absent provenance MUST return UNKNOWN. Record exact command, count, SHA, fixture IDs and output.
2. **Twin:** use a same-tenant SAN→storage→Payments path with independently sourced edges and a fixed `as_of`. Record path, edge source, observed time, graph version and freshness. Remove one edge, make one stale, or cross tenants: business impact MUST become UNKNOWN, not confirmed Payments outage.
3. **Analyst/Critic/RAG:** substitute nonexistent evidence hash, stale citation, tenant mismatch, and self-asserted Critic independence. Each MUST fail closed. Synthetic negative results do not qualify actual independent model review or production RAG.
4. **Policy/HITL:** simulate LIVE request with absent approval, stale owner/fencing, missing preconditions or unsupported effect: MUST DENY, no network call, no ITSM write, no executor dispatch. A fixture-level DENY is not a production effect audit.
5. **NOC/ITSM (after P0):** only read-only GET and explicit SIMULATION label; do not claim real ticket, CMDB authority or browser acceptance without separate receipts.

## Exact-head CI inventory (GitHub Actions read, 2026-11-16)

- #718 `5f8a3fb0`: adversarial correlation [43767943571](https://github.com/alimtalbi-ata/aiops/actions/runs/43767943571) **PASS**; synthetic qualification [43767943556](https://github.com/alimtalbi-ata/aiops/actions/runs/43767943556) **FAIL**; synthetic NOC [43767943551](https://github.com/alimtalbi-ata/aiops/actions/runs/43767943551) **FAIL**; quality [43767943576](https://github.com/alimtalbi-ata/aiops/actions/runs/43767943576) **FAIL**.
- #715 `3da16e91`: synthetic qualification [43742358029](https://github.com/alimtalbi-ata/aiops/actions/runs/43742358029) **PASS**; quality [43742358010](https://github.com/alimtalbi-ata/aiops/actions/runs/43742358010) **FAIL**.
- #716 `2d6b794a`: quality [43732445942](https://github.com/alimtalbi-ata/aiops/actions/runs/43732445942) **FAIL**; synthetic qualification [43732446134](https://github.com/alimtalbi-ata/aiops/actions/runs/43732446134) **FAIL**.
- #720 `f4023ae3`: synthetic qualification [43737651757](https://github.com/alimtalbi-ata/aiops/actions/runs/43737651757) **FAIL**; quality [43737651704](https://github.com/alimtalbi-ata/aiops/actions/runs/43737651704) **FAIL**.
- Previous architect #783 `d6f67056`: quality [43855199719](https://github.com/alimtalbi-ata/aiops/actions/runs/43855199719) **FAIL**.
- #713 exact head `91551be2`: no pull-request workflow run returned by SHA lookup; **NOT_TESTED**, not PASS.
- **Local commands this passage: NOT_TESTED.** No container, browser, networked runtime or E2E execution.

## Risks R1–R8 and S1–S8

| Risk | Blocker / owner |
|---|---|
| R1 | Cross-tenant correlation / Core |
| R2 | Duplicate or conflicting events / Core |
| R3 | Stale/untrusted graph provenance / Twin |
| R4 | False business causality / Twin |
| R5 | Fabricated or stale citations / Analyst |
| R6 | Critic independence only self-declared / Policy |
| R7 | HITL bypass or unauthorized effect / Policy |
| R8 | Base-SHA drift and #713 merge conflict / Architect |

S1 correlation, S2 dedup/identity, S3 Twin provenance, S4 business impact, S5 Analyst/Critic/HITL: **BLOCKED**. S6 NOC E2E and S7 ITSM E2E: **NOT_TESTED**. S8 LIVE: **BLOCKED / NO-GO**.

## Handoff and safe rollback

Core owns its test/workflow corrections; Twin owns graph contract; Policy owns Critic/HITL tests. Architect owns only this isolated ledger and PR #713 coordination. No shared-file edits, no merge/rebase/cherry-pick, no deployment/SSH/Debian, no V1 :7777/V30 :7788/LIVE modification, no new stack or cron. Requalify every changed SHA independently. Rollback is omission/revert of this standalone document only.
