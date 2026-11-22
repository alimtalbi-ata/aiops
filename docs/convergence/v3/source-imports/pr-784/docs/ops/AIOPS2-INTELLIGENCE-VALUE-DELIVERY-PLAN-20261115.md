# AIOPS2 — Intelligence value delivery plan (2026-11-15)

Status: PRODUCT/ENGINEERING PLAN — NOT runtime, CI or browser attestation.
Integration candidate: PR #713, `integration/aiops2-convergence-20261114`.
Objective: turn SAN P1 → Payments P2 from a static synthetic walkthrough into an **executed, independently testable, isolated AIOps intelligence pipeline**.

## Single prioritized backlog — WIP <= 3

| Priority | Epic / owner schedule | First increment | Acceptance and negative cases |
| --- | --- | --- | --- |
| P0-1 | Event ingestion and correlation / 3-of-5 | Versioned event envelope (source, source_event_id, tenant, CI, observed_at, known_at, severity, provenance), deterministic dedupe and SAN/Payments correlation | Same event ingested twice produces one canonical event; different tenant never correlates; missing/invalid source, stale evidence and conflicting CI fail closed; replay deterministic |
| P0-2 | Sourced Digital Twin impact / 3-of-5 | Explicit SAN → storage → application → Payments dependency edges with source and freshness, plus impact explanation | Verified edges only; absent or stale edge yields UNKNOWN rather than inferred production impact; cycle and cross-tenant tests |
| P0-3 | Analyst / Critic / evidence / 4-of-5 | Structured hypotheses linked to evidence IDs, contradictions and missing evidence; deterministic baseline before LLM | Critic rejects invented citations, conflicting or stale evidence and prompt-injection instructions; no hypothesis becomes Policy approval |
| P1 | Decision cockpit / 2-of-5 | One incident view: correlation explanation, impact path, evidence, hypotheses, critic objections, Policy disposition and next NOC action | Keyboard/mobile checks; explicit DEMO/REPLAY/SIMULATION; no mock labeled LIVE |
| P1 | ITSM / isolated E2E / 4-of-5 | Read-only GLPI reference and reproducible sandbox E2E | No GLPI writes, no infrastructure effects; test receipt bound to exact SHA |

Schedule 1-of-5 owns security/negative regression evidence; schedule 5-of-5 owns integration, scope and coordination.

## Eight-week indicative milestones (not delivery commitments)

- W1–W2: ingest, normalize, dedupe and correlate synthetic multi-source events with contracts and tests.
- W2–W4: source-attributed dependency graph and business impact, including UNKNOWN cases.
- W3–W6: evidence-linked Analyst/Critic, optional RAG only after ACL/provenance tests.
- W5–W7: decision cockpit and read-only ITSM projection from actual sandbox pipeline outputs.
- W7–W8: isolated end-to-end regression, reproducible receipts and customer-demo review.

## First vertical slice — SAN P1 → Payments P2

1. Feed **synthetic** SAN and Payments events through a real in-process correlation implementation.
2. Generate a canonical incident and attach evidence IDs and provenance.
3. Resolve business impact through explicit, sourced Twin edges; return UNKNOWN for missing edges.
4. Generate structured Analyst hypotheses and Critic disposition; separate hypotheses from facts.
5. Display the computed result in the cockpit with a deterministic Policy DENY for LIVE.
6. Optionally prepare an ITIL Problem/PIR draft, without writing to GLPI.

**Definition of done**: runnable isolated tests on exact commit; evidence of dedupe, tenant isolation, stale/contradictory data, unauthorized action denial, deterministic replay, browser UX; honest PASS/FAIL/BLOCKED/NOT_TESTED report. A fixture checksum is not an authenticated runtime attestation.

## Coordination protocol for the five ChatGPT schedules

- 1/5 Quality: contract, security, evidence, cross-tenant and failure-path tests; report exact test commands/results.
- 2/5 UX: accessible decision cockpit consuming computed outputs, not fabricated live status.
- 3/5 Sources: correlation engine and sourced Twin edges; no production network or database changes.
- 4/5 Intelligence: evidence-backed Analyst/Critic and isolated E2E tests; no real effects.
- 5/5 Architect: enforce WIP <= 3, avoid overlapping file edits, review PRs and report SHA, owner, acceptance criteria and blockers.

Every run must identify **actual changes** (PR/SHA), **actually executed tests**, remaining UNKNOWNs and one concrete next step. Do not claim that scheduling a run means its engineering work completed.

## Non-negotiable boundaries

No merge, rebase, cherry-pick, deployment, SSH, Debian or LIVE operations. V1 :7777 untouched; V30 :7788 is not modified by this plan. No new cron, parallel runtime, secret exposure or real GLPI writes. No LIVE remediation. CI, browser, real data and runtime remain NOT_TESTED/UNKNOWN until independently evidenced. Policy/HITL remain fail-closed. NO-GO LIVE.
