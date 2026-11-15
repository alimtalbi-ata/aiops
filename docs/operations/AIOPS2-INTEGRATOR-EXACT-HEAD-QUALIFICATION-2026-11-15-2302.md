# AIOPS2 — integrator exact-head qualification, 2026-11-15 23:02 CET

**Scope:** DEV/source-only review; **NO-GO LIVE**. Single integration candidate `integration/aiops2-convergence-20261114`, observed HEAD `36b2872f2900c19945a1b0472f7d60eff5c3e02a` (#713, DRAFT, mergeable=false). No merge, rebase, cherry-pick, deployment, SSH or host qualification. No change to V1 :7777, V30 :7788, or external effects. Synthetic results must remain explicitly labelled DEMO/SIMULATION. UNKNOWN means unverified, not healthy.

## P0 WIP 3/3 — exact SHA and CI receipts

| Priority / owner | PR / exact head SHA | Exact-head GitHub Actions receipts | Decision / next |
|---|---|---|---|
| 1 Correlation / Core 3/5 | [#718](https://github.com/alimtalbi-ata/aiops/pull/718) `a0a4b541efe97ae06090be20066810273b64f08c` | [43762105337](https://github.com/alimtalbi-ata/aiops/actions/runs/43762105337) PASS; [43762105361](https://github.com/alimtalbi-ata/aiops/actions/runs/43762105361) PASS; [43762105474](https://github.com/alimtalbi-ata/aiops/actions/runs/43762105474) FAIL | BLOCKED; Core fixes failing job and provides tenant isolation, idempotency, identity trace negative-case receipts |
| 2 Twin impact / Twin 1/5 | [#715](https://github.com/alimtalbi-ata/aiops/pull/715) `3da16e9177bf6afbacfd79742b7f910663e95c4d` | [43742358029](https://github.com/alimtalbi-ata/aiops/actions/runs/43742358029) PASS; [43742358010](https://github.com/alimtalbi-ata/aiops/actions/runs/43742358010) FAIL | BLOCKED; Twin demonstrates deterministic, provenance/freshness-checked SAN→Payments impact and missing-edge UNKNOWN |
| 3 Analyst/Critic/RAG / Policy 4/5 | [#716](https://github.com/alimtalbi-ata/aiops/pull/716) `2d6b794a2fdd2cb4862197a7c39d9fe03ef708a2`; [#720](https://github.com/alimtalbi-ata/aiops/pull/720) `f4023ae3571bc4b55025a5243bd1a9bc6c05fb26` | #716 [43732445942](https://github.com/alimtalbi-ata/aiops/actions/runs/43732445942) FAIL, [43732446134](https://github.com/alimtalbi-ata/aiops/actions/runs/43732446134) FAIL; #720 [43737651757](https://github.com/alimtalbi-ata/aiops/actions/runs/43737651757) FAIL, [43737651704](https://github.com/alimtalbi-ata/aiops/actions/runs/43737651704) FAIL | BLOCKED; Policy proves grounded citations, independent Critic, stale/missing evidence denial and HITL no-effect |

**Downstream, not P0 WIP:** UX 2/5 [#719](https://github.com/alimtalbi-ata/aiops/pull/719) HEAD `0d702bb11c20f2befc4994c373337200cf286b87`: [43763074111](https://github.com/alimtalbi-ata/aiops/actions/runs/43763074111) PASS, [43763074241](https://github.com/alimtalbi-ata/aiops/actions/runs/43763074241) FAIL. NOC/ITSM consumption is gated on the three upstream contracts. Integrator 5/5 [#730](https://github.com/alimtalbi-ata/aiops/pull/730) HEAD `3a04d893cd0394b4b8627ed77e0d5dacd27dc6d4`: [43761658707](https://github.com/alimtalbi-ata/aiops/actions/runs/43761658707) FAIL. #713 exact-head PR-triggered workflow runs returned **none** in the connector query; status **NOT_TESTED**, not PASS. Source review and GitHub run metadata only; job-level root cause **UNKNOWN** pending log inspection.

## File ownership and interface gates

GitHub changed-file enumeration: #718 owns `tests/test_aiops2_correlation_adversarial_contract.py` and `.github/workflows/aiops2-adversarial-correlation.yml`; #715 owns `scripts/aiops2_twin_dependency_read.py` and its contract/test; #716 owns `scripts/aiops2_critic_negative_gate.py` and its contract/test; #720 owns `scripts/aiops2_sandbox_chain_receipt.py` and its contract/test; #719 owns `scripts/aiops2_noc_decision_cards.py`, its tests and UX qualification document. No identical changed paths among those five PRs in this enumeration; **semantic/API compatibility remains NOT_TESTED**, and #713 changes central Core/Portal/workflow files. Do not alter another owner's paths. Each owner must state schema/version, tenant+actor, mode, source ID, event time, evidence provenance/freshness, UNKNOWN semantics, error response and zero-effect fallback. Confirm shared IDs end-to-end before accepting UI snapshots.

## S1–S8 and risks

| Milestone | Gate / status |
|---|---|
| S1 source contract and identity | BLOCKED — correlation exact-head CI FAIL |
| S2 dedup and tenant-isolated correlation | BLOCKED — negative-case evidence incomplete |
| S3 Twin impact and provenance | BLOCKED — Twin exact-head CI FAIL |
| S4 Analyst/Critic/RAG grounded chain | BLOCKED — two Policy PRs CI FAIL |
| S5 deterministic Policy/HITL no-effect | BLOCKED — negative-case qualification pending |
| S6 cockpit NOC / ITSM consumption | NOT_TESTED E2E; UX quality CI FAIL |
| S7 customer journey repeatability / business KPI | NOT_TESTED — no same-SHA E2E |
| S8 integration/release decision | BLOCKED — #713 DRAFT, mergeable=false, LIVE NO-GO |

Risks: R1 cross-tenant false join (Core, zero tolerated); R2 stale/missing graph edge represented as fact (Twin, require UNKNOWN); R3 fabricated citation or Critic bypass (Policy, deny); R4 unsafe HITL/external effect (Policy, fail closed); R5 shared CI quality failure (Core/CI, diagnose exact job before changes); R6 divergent #713 integration base (5/5, inspect conflict, no automatic merge); R7 cockpit premature confidence (UX, label synthetic); R8 lack of runtime/business E2E (5/5, no GO).

**Business acceptance:** (1) zero cross-tenant joins and stable Event→Incident→Run→Evidence links; (2) reproducible SAN→Payments blast radius with source/version/timestamp, explicit UNKNOWN for gaps; (3) citation-to-evidence integrity and independent Critic; (4) denied HITL has zero external effects. These are targets, not observed PASS.

**Next:** Core/CI isolates the failing quality step at #718's exact SHA; Twin and Policy deliver negative-case artifacts at their heads; integrator reviews contracts and reruns CI on any new SHA. No candidate promotion before every required check PASS and explicit rollback. **Rollback for this document:** revert its isolated commit only; no runtime change.
