# AIOPS2 — product acceptance receipt, 2026-11-16 02:01 CET

Scope: **DEV / isolated synthetic only**. This is a review contract, **not** evidence of execution, a deployment authorization, or a LIVE qualification. No secrets, external side effects, new stack, scheduler or runtime changes. V1 :7777 and V30 :7788 untouched. **NO-GO LIVE**.

## Single P0 queue (WIP 3/3)

| Order / owner | Exact PR HEAD at observation | Evidence from GitHub Actions at this HEAD | Acceptance to request |
|---|---|---|---|
| 1 Correlation / Core 3/5 | #718 `5f8a3fb00882d7cbfc1ca164ed4bf19173e6d404` | PASS offline adversarial #43767943571; FAIL synthetic #43767943556, NOC #43767943551, quality #43767943576 | Same tenant+entity+time+source trace joins; cross-tenant or mismatched entity MUST NOT join; no evidence -> UNKNOWN; record false-join count = 0 on deterministic negative fixtures |
| 2 Twin / Twin 1/5 | #715 `3da16e9177bf6afbacfd79742b7f910663e95c4d` | PASS synthetic #43742358029; FAIL quality #43742358010 | SAN→storage→Payments path must include timestamp, provenance, confidence and trace; stale/missing edge => UNKNOWN, never asserted impact |
| 3 Analyst/Critic/RAG / Policy 4/5 | #716 `2d6b794a2fdd2cb4862197a7c39d9fe03ef708a2`, #720 `f4023ae3571bc4b55025a5243bd1a9bc6c05fb26` | #716 FAIL #43732445942/#43732446134; #720 FAIL #43737651704/#43737651757 | Every recommendation has independently checkable citation, Critic separately rejects absent/stale/foreign-tenant evidence, HITL denial produces zero external effects |

Downstream only: NOC #719 `16f79df6f8f55010d7f8a240f20cc627c9973170`: PASS synthetic NOC #43769423138 and synthetic qualification #43769423068; FAIL quality #43769423108. ITSM remains downstream; do not open fourth P0.

## Cross-team contract gates before proposing integration

1. **Identity**: correlation output must carry a stable incident/run ID, tenant ID, source event IDs and time window. Twin and intelligence must reject or mark UNKNOWN when any required identity/provenance is missing. Negative fixture: two otherwise identical events with distinct tenant IDs never correlate.
2. **Business impact**: Twin consumes canonical identity and produces a read-only dependency path with edge provenance, observation time, freshness and UNKNOWN for missing/stale evidence. Negative fixture: remove one SAN→Payments dependency edge; expected result is UNKNOWN, not an invented Payments outage.
3. **Reasoning & governance**: Analyst consumes evidence references only; Critic independently checks each citation against the same tenant/run and observation window. Negative fixture: citation from a different tenant or outside freshness threshold is rejected; HITL deny path must not call external adapters.
4. **UX/ITSM**: NOC displays evidence state and explicit SIMULATION/DEMO markers, never a LIVE-ready badge from synthetic evidence. No write path to GLPI or other ITSM without policy authorization and operator HITL.
5. **Integration**: for each proposed SHA, record test command, fixture, expected/observed result, CI run URL, rollback/revert and changed-file collision check. One successful job is insufficient if another required job fails.

## Risk register and milestones

| Risk | Owner | Mitigation / current verdict |
|---|---|---|
| R1 cross-tenant false join | Core | deterministic adversarial fixtures; BLOCKED |
| R2 stale/unsourced impact | Twin | negative edge and freshness fixtures; BLOCKED |
| R3 unsupported AI citation | Policy | independent citation rejection; BLOCKED |
| R4 unapproved external action | Policy/HITL | deny/no-side-effect proof; BLOCKED |
| R5 quality gate regression | Core/CI | fix existing test/workflow mismatch on owned branch, no new schedule; BLOCKED |
| R6 PR #713 divergence | Architect | exact-head interface and collision review; BLOCKED |
| R7 NOC synthetic mistaken for LIVE | UX | visible mode labels, no LIVE promotion; BLOCKED |
| R8 absent runtime/rollback receipt | Operator UID1001 | host evidence only via authorized host tool; NOT_TESTED |

S1 identity/correlation BLOCKED; S2 negative isolation BLOCKED; S3 Twin provenance BLOCKED; S4 impact UNKNOWN BLOCKED; S5 Analyst/Critic/HITL BLOCKED; S6 NOC NOT_TESTED E2E; S7 ITSM NOT_TESTED E2E; S8 integrated release/rollback BLOCKED.

## CI and rollback receipt

At observation, PR #738 `f8b5b10174e90d5c3acc49edca6ca76c0e8c4c6b` quality run #43778388399 is **FAIL** (previously in progress). PR #713 HEAD `931cd107439c2180acb143f9198ed84649443b3f` has **no PR workflow runs returned** by commit lookup; verdict **NOT_TESTED**, not PASS. #713 remains DRAFT/non-mergeable. All these states are point-in-time and must be refreshed before any promotion.

This document's own tests: **NOT_TESTED** until its exact commit has an observed result. Rollback: revert only the documentation commit in this dedicated PR; no runtime changes.

Next: Core owns CI quality fix; Twin and Policy deliver negative-case receipts; Architect reviews interfaces and exact SHA after updates. **No automatic merge, deployment, rebase, cherry-pick, SSH or Debian access.**
