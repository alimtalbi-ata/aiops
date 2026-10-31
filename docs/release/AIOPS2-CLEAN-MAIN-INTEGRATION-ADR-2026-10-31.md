# ADR-INT-2026-10-31 — single clean main-based AIOps2 candidate and selective integration

**Snapshot:** 2026-10-31 22:08 Europe/Paris (21:08 UTC). **Owner:** Architect 5/5. **Status:** DRAFT / SOURCE_REVIEWED / RELEASE_STABLE=NO_GO. **Scope:** DEV only; no host, GLPI real write, executor or LIVE.

## Decision and exact base

- The **only promoted integration candidate** is `integration/enterprise-slice-main-20261031-2208`, created from **main `780a8e03b32e0a3969fc36f6aeee69bacb5b45ab`**. This document-only first commit is not an integrated application build.
- Historical #201 (`fbcb5a35e916199ff82e83193a95d6d93fdacfb3`, old main `27deb9b1a66faf27df8d69b137a63451f7649d80`, 112 ahead / 3 behind current main) remains an **unmerged Draft SOURCE branch**, not a second release candidate. No wholesale merge of #201, #195 or #204.
- #195 is **closed / superseded**; architecture/reference, reuse register and execution board are now maintained from the selective main baseline (#224/#225) and this candidate.
- main protection is reported disabled; manual gates are mandatory even if GitHub permits a merge. #221/#224/#225 already merged. Main post-merge #225 Quality [#41242016327](https://github.com/alimtalbi-ata/aiops/actions/runs/41242016327) = **3/3 SUCCESS** on the exact main SHA above. This is D0 for main, not D1-D4.

## P0 WIP limit and exclusive contracts

| Priority | Single owner | Scope, exclusive files and acceptance | Source, head at snapshot | Gate/blocker |
|---|---|---|---|---|
| P0-1 actor+tenant Portal ACL | 2/5 Portal | `app/portal/**`, Portal API/HTML/JS tests. Do not fetch Core Run, NOC, Copilot or GLPI links before server-verified actor, tenant and exact Run ACL; absent/foreign/stale must remain indistinguishable 503 UNKNOWN. No browser bearer authority. | #202 `4c1ffed252051ad630d309339de59f85e41b63a9` (43 ahead/3 behind main, historical Quality 3/3); #223 `9d3ee6fedd23171e00bffa141b839bf2031aa964` (Draft, stacked on #201, Quality 3/3) | Core actor/tenant read contract not yet integrated. No positive ACL claim. |
| P0-2 Core xref/Evidence + migration | 3/5 Core | `app/core/itsm_xref.py`, `app/shared/core_itsm_xref_read.py`, Core API and tests; coordinate shared `app/core/main.py` via architect only. Read-only GLPI authority, actor+tenant permission, exact ticket/Run/CI, signed source entity provenance and freshness. Reserve migration ordinal 012 for xref after 009 AI, 010 Evidence, 011 HITL. | #205 `537b75dd4b10fb56791d8e59095fcdea0dd62e0d` (57 ahead/3 behind, **0 exact-head check runs**); #212 migration 012 Draft | CMDB entity tampering accepted by blast-radius contract; 3 adversarial tests not wired; 009 collision. |
| P0-3 HITL/PG16 DR | 4/5 Policy | `app/worker/**`, Policy/HITL tests, outbox/Temporal; shared Core changes only through architect. Require PG16 pg_dump/pg_restore, lease/fence/retry/ACK, restart, zero effect. | #204 `5285aec4359a8132cb6c5801dc8d3a18118930fc` (Draft on #194, 902 ahead/46 behind main); Quality [#41241099554](https://github.com/alimtalbi-ata/aiops/actions/runs/41241099554) 6/6 and 3 qualification workflows SUCCESS | Parent #194, migration 011 and integrated identity still absent. No human/live approval claim. |

**Queued, not extra P0 WIP:** 1/5 ACME #198 `d3596cb0f42ea96a6ba8c7d9693372e3ffc44eff` (49 ahead/3 behind, [Quality #41241023119](https://github.com/alimtalbi-ata/aiops/actions/runs/41241023119) 3/3, but **three new type-override tests not exercised**); owns only `tools/generate_acme_incidents.py`, ACME fixtures/tests/story. Then release kit #206/#210/#213, and benchmark #196 (FAIL until qualified model/evaluator repetitions, provider-reported tokens only, cost UNKNOWN without versioned tariff).

## Integration order (no bulk merges)

1. **Baseline/ownership:** retain main's #221 schedule, #224 architecture and #225 board. Keep this branch as the sole candidate; owner branches target it only through **focused PRs**, never direct pushes. No merge of a Draft or unqualified PR.
2. **Portal negative security boundary first:** port only the needed #202 Run detail/ACL safeguards and #223 NOC generation fence, with overlapping `app/portal/main.py` resolved by Portal owner; preserve 401/403/503, no-upstream-on-deny and browser race tests. Keep positive access disabled until step 3.
3. **Core positive read contract:** fix CMDB entity-provenance tamper, run adversarial tests and disposable PostgreSQL 16, then reconcile migrations **009 AI → 010 Evidence → 011 HITL → 012 ITSM xref**. Never import #205's conflicting `009_itsm_xref_read.sql` as 009. Include forward and rollback tests on disposable DB, with evidence read-back same tenant/actor/Run.
4. **Join Portal/Core:** only enable positive exact-Run read once the server actor+tenant contract is integrated; qualify D1 with same commit SHA, then D2 browser/API with synthetic ACME tenant and foreign-tenant negatives.
5. **HITL:** selectively port #194 prerequisite contract then #204 fault injection/PG16/Temporal; no separate Core ledger, no fake approval authority, `execution_allowed=false`, `effect_allowed=false` for synthetic. Requalify D1/D2 on changed candidate SHA.
6. **ACME:** port graph-bound #198 generator, pinned 005 seed, type-override tests explicitly invoked in CI, same IDs through Event→Incident→Twin impact→Analyst/Critic→Evidence→Policy/HITL→SIMULATE→verify→resolve/reopen, plus ITIL Service Desk/Problem/Change/Knowledge. No GLPI write real.
7. **Release kit:** compare #206, #210, #213 as *distinct* source branches; do not infer kit validity from CI. Require manifest **68 JSON entries**, **407 SHA** baseline as applicable, version/provenance, SHA and size for every entry, extract/repack and clean sandbox install/upgrade/rollback (D3). No re-audit absent changed artifact.
8. **Promotion:** only after fresh exact-head D0, combined D1, same-SHA D2, D3 and customer D4 sign-off; verify PR non-Draft, mergeable, unchanged base and expected_head_sha. Merge only through reviewed PR, never reset/force push main. Post-merge exact-main CI required.

## Required reproducible commands / evidence

- At each handoff: `git rev-parse main`, `git merge-base main <head>`, `git diff --name-status main...<head>`, exact commit check-runs, artifact ID/checksum and run URL. A passing job does not imply that every newly added test executed.
- Portal focused: `python -m unittest discover -s tests -p 'test_portal_run_detail.py' -v`; `node --test tests/test_portal_noc_client.cjs`; then hosted browser/API same-SHA CI.
- Core focused: `python -m unittest discover -s tests -p 'test_core_itsm_xref_api.py' -v`, `python -m unittest discover -s tests -p 'test_core_itsm_xref_read.py' -v`; PG16 integration only in explicit disposable CI.
- HITL focused: `python -m unittest discover -s tests -p 'test_hitl_failure_injection.py' -v`; PG16/Temporal/DR only in disposable CI, never on host.
- ACME focused: `python -m unittest discover -s tests -p 'test_acme_fixture_override_types.py' -v`, `python -m unittest discover -s tests -p 'test_acme_synthetic_incident_catalog.py' -v`.
- Release: deterministic manifest checker, SHA256 sidecar, semantic JSON check, extract/repack, sandbox install/upgrade/rollback; record **N/N** separately for each gate. Commands listed here are **planned**, not executed by this documentation commit.

## Automation and runtime truth

- A Debian SRV-DEB-05 cron `*/1`: **UNATTESTED**; inventory user, cwd, PATH, lock, timeouts, logs, exit, retries, secrets, heartbeat before any installation. No SSH/sudo.
- B GitHub daily `23 2 * * *` UTC and manual dispatch: versioned on main via #221; post-merge PR/push Quality 3/3, but **no schedule firing/heartbeat proven**. No self-hosted runner.
- C five ChatGPT schedules: enabled, hourly configured; **all `next_run_time=null`**, so recurrence not guaranteed. Last handoffs must be compared with exact GitHub SHA each cycle.
- D lab ACME/Chromium/PG16/Temporal: synthetic/disposable only, not observed Debian/NGX/GLPI runtime. Offline heartbeat gate is not a deployed heartbeat.

## Revert, stop conditions and qualification

- Documentation-only candidate can be abandoned with **no runtime or DB rollback**; revert its focused commit(s) via PR if promoted.
- Each later focused change must include file-level revert commit and a tested **disposable** DB down/restore recipe before integration; stop on ordinal collision, tenant leak, stale source, untrusted actor, checksum mismatch, failed CI, missing checks, Draft or changed SHA.
- Evidence states: **SOURCE_REVIEWED** for source/patch inspection; **CI_PASS** only for exact SHA/check names; **INTEGRATION_PASS** only for D1/D2 receipts; **RUNTIME_OBSERVED** only with direct timestamped runtime evidence; otherwise **NOT_VERIFIED**.
- D0 main only **CI_PASS 3/3**; D0 on this candidate **PENDING** until its own commit checks; D1 **NOT_QUALIFIED**; D2 **NOT_QUALIFIED**; D3 **NO_GO**; D4 **NOT_ATTESTED**. **RELEASE_STABLE=NO_GO**.
