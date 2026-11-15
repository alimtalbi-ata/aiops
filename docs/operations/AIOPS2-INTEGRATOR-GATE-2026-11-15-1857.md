# AIOPS2 integrator gate — 2026-11-15 18:57 Europe/Paris

Owner: 5/5 architect. Scope: DEV documentation and review only. Candidate: `integration/aiops2-convergence-20261114` / PR #713, observed HEAD `6923e7ebf0b696868ba74f0ec205494977eaf06b`. **NO-GO LIVE**. No merge, deployment, migration, SSH, host action or V1/V30 change.

## Single ordered P0 backlog — WIP 3/3

| Order / owner | PR / observed HEAD | Product acceptance | Integration gate |
| --- | --- | --- | --- |
| 1 Correlation / Core 3/5 | #718 `4385ee22c02e104e6701785024706d832968a947` | Deterministic event→incident→run→xref→evidence; zero cross-tenant joins, explicit UNKNOWN for absent/stale provenance; dedup counts reported | BLOCKED: exact-head Actions #43733960516 and #43733960413 FAIL |
| 2 Digital Twin / Twin 1/5 | #715 `3da16e9177bf6afbacfd79742b7f910663e95c4d` | Source-backed, tenant-scoped SAN→storage→Payments path with timestamp, graph version, impact and uncertainty; fixture attestation is NOT LIVE | BLOCKED: #43742358029 SUCCESS but #43742358010 FAIL on same HEAD; identify failed gate |
| 3 Analyst/Critic/RAG / Policy 4/5 | #716 `2d6b794a2fdd2cb4862197a7c39d9fe03ef708a2`; #720 `f4023ae3571bc4b55025a5243bd1a9bc6c05fb26` | Independent Critic, grounded citations, no invented evidence, explicit HITL DENY, no external effects in simulation | BLOCKED: #716 Actions #43732445942/#43732446134 FAIL; #720 #43737651757/#43737651704 FAIL |

Cockpit NOC / UX 2/5: #719 `912440fc73588d363feabc09cecda052532d55e4`, Actions #43735071906/#43735071908 FAIL; queue after P0 contracts, not fourth WIP. ITSM remains downstream. #717 integrator acceptance docs HEAD `e51b8e33f9e0e23b154ed66e8c3dcc60eabc853c`, Actions #43738614344 FAIL.

## Interface and collision review

- PR #713 already changes `scripts/aiops2_event_correlation.py`, `scripts/aiops2_digital_twin_impact.py`, `scripts/aiops2_analyst_critic.py` and NOC rendering. Treat these as owned integration surfaces; contributors must not overwrite them.
- #718 adds only `tests/test_aiops2_correlation_adversarial_contract.py` and consumes the candidate correlation API; check against current #713 HEAD, not merely the earlier PR base.
- #715 adds separate Twin read module, test and contract; distinguish fixture-provided `attested` from verified GLPI/CMDB attestation. Check contract alignment with the candidate Twin impact schema.
- #716 and #720 add distinct scripts/tests/docs; compare citation/tenant/mode/deny schemas before wiring. #719 adds a distinct renderer and is held downstream.
- #717 modifies only integration acceptance/CI-triage docs. This gate note uses a new dedicated file to avoid concurrent edits.
- PR metadata reported earlier base SHA values for child PRs, but current candidate HEAD differs. Re-evaluate ancestry and test exact candidate HEAD before promotion; mergeability alone is insufficient.

## Risk register

| Risk | Owner | Gate / mitigation |
| --- | --- | --- |
| R1 Cross-tenant identity or stale xref | Core 3/5 | Adversarial negative tests, 0 cross-tenant joins |
| R2 Unsupported causal impact | Twin 1/5 | Versioned path, freshness, provenance, UNKNOWN on broken links |
| R3 Hallucinated citations or unsafe autonomy | Policy 4/5 | Independent Critic, verified receipts, deterministic HITL DENY |
| R4 NOC/ITSM outruns backend contracts | UX 2/5 | Defer UI integration until upstream schemas pass |
| R5 CI failures and changing base SHA | Integrator 5/5 | Exact-head per-job diagnosis, no PASS-by-proxy |
| R6 LIVE/DEMO boundary violation | Integrator 5/5 | NO-GO LIVE, simulation no effects, no host action |

## Milestones S1–S8 (unattested until receipt)

S1 identity contract; S2 correlation adversarial gate; S3 Twin graph and impact; S4 Analyst citations; S5 Critic and Policy/HITL; S6 NOC/ITSM projection; S7 deterministic synthetic SAN→Payments chain; S8 end-to-end evidence package and reviewed promotion. All: **NOT_TESTED as end-to-end milestones**; isolated CI outcomes above do not constitute milestone PASS.

## Next action / rollback

1. Core: repair #718 exact-head CI and provide 0 false joins evidence. Twin: identify the failing job on #715 and provide graph/path acceptance. Policy: resolve #716/#720 failing checks and reconcile citation schema. UX: hold #719.
2. Integrator: inspect each failed job and compare new HEADs to PR #713, record measurable synthetic receipts, then consider review-only promotion. No automatic merge.
3. Rollback for this documentation increment: revert its single commit on the dedicated branch; no runtime changes.
