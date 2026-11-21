# AIOPS2 — exact-head CI triage and product acceptance (2026-11-16 05:58 CET)

Scope: DEV documentation only, no runtime action. Base: `integration/aiops2-convergence-20261114` at `931cd107439c2180acb143f9198ed84649443b3f`. This record does not qualify LIVE.

## One P0 backlog (WIP 3/3)

| Order / owner | PR / exact head | Evidence on that head | Business acceptance / next evidence |
|---|---|---|---|
| 1 Correlation / Core 3/5 | #718 `5f8a3fb00882d7cbfc1ca164ed4bf19173e6d404` | offline adversarial [43767943571](https://github.com/alimtalbi-ata/aiops/actions/runs/43767943571) PASS; synthetic [43767943556](https://github.com/alimtalbi-ata/aiops/actions/runs/43767943556) FAIL; NOC [43767943551](https://github.com/alimtalbi-ata/aiops/actions/runs/43767943551) FAIL; quality [43767943576](https://github.com/alimtalbi-ata/aiops/actions/runs/43767943576) FAIL | Zero cross-tenant joins on explicit negative fixtures; event→incident→run→evidence identity and dedup receipts; provide test command/output |
| 2 Digital Twin / Twin 1/5 | #715 `3da16e9177bf6afbacfd79742b7f910663e95c4d` | synthetic [43742358029](https://github.com/alimtalbi-ata/aiops/actions/runs/43742358029) PASS; quality [43742358010](https://github.com/alimtalbi-ata/aiops/actions/runs/43742358010) FAIL | SAN→Payments impact with source ID, tenant, observed_at, freshness threshold, confidence and UNKNOWN for stale/missing graph |
| 3 Analyst/Critic/RAG / Policy 4/5 | #716 `2d6b794a2fdd2cb4862197a7c39d9fe03ef708a2`; #720 `f4023ae3571bc4b55025a5243bd1a9bc6c05fb26` | #716 [43732445942](https://github.com/alimtalbi-ata/aiops/actions/runs/43732445942), [43732446134](https://github.com/alimtalbi-ata/aiops/actions/runs/43732446134) FAIL; #720 [43737651704](https://github.com/alimtalbi-ata/aiops/actions/runs/43737651704), [43737651757](https://github.com/alimtalbi-ata/aiops/actions/runs/43737651757) FAIL | Citation IDs resolve to independent immutable evidence; Critic challenges invalid claims; missing approval/fencing/ownership means deny and zero external effects |

NOC #719 `16f79df6f8f55010d7f8a240f20cc627c9973170` downstream only: synthetic NOC [43769423138](https://github.com/alimtalbi-ata/aiops/actions/runs/43769423138) PASS; synthetic qualification [43769423068](https://github.com/alimtalbi-ata/aiops/actions/runs/43769423068) PASS; quality [43769423108](https://github.com/alimtalbi-ata/aiops/actions/runs/43769423108) FAIL. ITSM downstream, no fourth P0.

## Shared CI blocker and ownership

Job-level inspection of #755 quality [43801492142](https://github.com/alimtalbi-ata/aiops/actions/runs/43801492142), #718 [43767943576](https://github.com/alimtalbi-ata/aiops/actions/runs/43767943576), #715 [43742358010](https://github.com/alimtalbi-ata/aiops/actions/runs/43742358010), #716 [43732445942](https://github.com/alimtalbi-ata/aiops/actions/runs/43732445942): each has `policy-and-static` FAIL specifically at `Daily quality schedule contract`; `grafana-real-integration` and `core-postgres-noc-real-integration` jobs report success **within those runs only**. This common failure does not imply the business tests pass. Core/CI owns reconciliation of existing test/workflow; avoid edits by Twin, Policy, NOC or architect to the same test/workflow. Do not add cron or schedule. Re-run exact-head gates after change.

#713 head `931cd107439c2180acb143f9198ed84649443b3f`: DRAFT, mergeable=false; PR-triggered runs returned none (NOT_TESTED, not PASS). #755 `b3ed2898750e6b17cadc3e906e7b915c4fb5693e` quality [43801492142](https://github.com/alimtalbi-ata/aiops/actions/runs/43801492142) FAIL.

## Interface gates, risks and S1–S8

- Core→Twin: tenant-scoped canonical incident/CI/service identifiers, source timestamps, no guessed joins (R1 cross-tenant, R2 stale CMDB).
- Twin→Analyst: graph version, impact provenance and freshness, explicit UNKNOWN (R3 fabricated impact).
- Analyst/Critic→Policy: independently resolvable citations, adversarial critic verdict and missing-proof rejection (R4 hallucination, R5 critic coupling).
- Policy/HITL→NOC/ITSM: proposed vs approved vs executed vs verified separate; fail-closed, no external effect in DEMO/SIMULATION (R6 unsafe effect, R7 approval/fencing).
- Integration: PR base drift, non-green exact-head CI, no LIVE evidence (R8). Require contract fixture replay across exact heads before acceptance.

S1 identity/correlation BLOCKED; S2 Twin impact BLOCKED; S3 Analyst grounding BLOCKED; S4 Critic/Policy/HITL BLOCKED; S5 cross-service contracts BLOCKED; S6 NOC E2E NOT_TESTED; S7 ITSM E2E NOT_TESTED; S8 LIVE BLOCKED / NO-GO. Each gate needs an executable test name, exact SHA, terminal result, artifact and a negative case. Synthetic PASS is not a production receipt.

No merge, rebase, cherry-pick, deployment, SSH, Debian, V1 :7777, V30 :7788 or LIVE changes. Revert only this documentary commit if withdrawn.
