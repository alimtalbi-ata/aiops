# NOC SAN → Payments — evidence-to-decision acceptance contract (2026-11-16)

Owner: 2/5 UX. Target: integration/aiops2-convergence-20261114, PR #713. **Design/qualification contract only; no runtime integration or LIVE attestation.**

## Decision-facing projection

Render an incident as a read-only, accessible operator decision: correlation count and member alert IDs; source/mode/time for each alert; SAN → intermediate CI → Payments path with graph version; evidence IDs and observation times; explicit uncertainty; Analyst hypothesis and Critic counter-hypothesis with their supporting/missing evidence; deterministic Policy result; HITL state; and next safe NOC action (inspect/escalate, never execute). Separate observed facts, synthetic estimates, and model hypotheses.

## Fail-closed provenance matrix

| Case | Expected impact label | Policy/HITL |
| --- | --- | --- |
| No evidence IDs, missing source, or empty path node | UNKNOWN | DENY_LIVE / REQUIRED |
| Evidence ID absent, duplicated, or mismatched to path | UNKNOWN | DENY_LIVE / REQUIRED |
| Graph version missing/mismatched | UNKNOWN | DENY_LIVE / REQUIRED |
| Observation time missing, malformed, future, or older than declared freshness limit | UNKNOWN | DENY_LIVE / REQUIRED |
| Evidence mode LIVE or mixed-mode input to synthetic projection | UNKNOWN | DENY_LIVE / REQUIRED |
| All synthetic references internally consistent and fresh | CONSISTENT_SYNTHETIC_ONLY, **not** source-attested | DENY_LIVE / REQUIRED |
| Analyst and Critic disagree, or confidence missing | Show both with UNKNOWN resolution | DENY_LIVE / REQUIRED |
| Empty incident inventory | Empty/UNKNOWN state, no fabricated P1 | DENY_LIVE / REQUIRED |

**Important:** Internal consistency is not authentication of upstream CMDB/monitoring, proof of correlation causality, or authorization. The UI must never promote a synthetically sourced path to a LIVE-verified path.

## Browser acceptance and artifact manifest

At widths **320, 768, 1440 px**, run isolated Chromium against the rendered sandbox output with network egress blocked. Assert no horizontal overflow; headings and landmarks; keyboard focus order; text zoom 200%; distinguishable Analyst/Critic/Policy/next-action sections; screen-reader names; no executable LIVE control; escaped HTML payloads in alerts, hypotheses and CI labels. Record exact HEAD SHA, command, exit code, browser version, test counts, screenshot filenames, SHA-256, viewport, seed, mode, and provenance of fixture/run. Accessibility assistive-technology verification is separate and remains UNKNOWN until performed.

## Dependency and handoff

- #713: authoritative projection and identity joins; do not modify its owned files concurrently.
- #719/#735/#739/#743: stacked UX test proposals require ancestry/diff reconciliation by architect before selective integration; avoid wholesale PR merges.
- Evidence/CMDB owner: supply authenticated source IDs, timestamps, graph version and documented freshness policy before any label stronger than synthetic consistency.
- Policy/HITL owner: deterministic fail-closed decision, never inferred from Analyst text.

**Qualification status:** This document is a specification, not executed browser proof. CI/browser/screenshots: UNKNOWN until exact-SHA evidence is attached. No deployment, host access, V1/V30 modification, real effects or LIVE claims. Rollback: omit this documentation-only PR.
