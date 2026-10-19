# AIOps 2.0 — Project Continuity Record

**Author:** Abdelhalim Talbi  
**Repository:** https://github.com/alimtalbi-ata/aiops  
**Default branch:** `main` (protected by workflow; work on branches and propose PRs)  
**Last updated:** 2026-10-19

## Why this document exists

This is the restart point for future ChatGPT sessions and contributors. Read it before proposing work. Update it whenever a material decision, architecture, interface contract, operational discovery, test result, or delivery changes. Do not rely on chat history as the only record.

## Current direction

Consolidate AIOps 2.0 around one coherent runtime and operations experience. Reuse proven historical AIOps v1 / V145 capabilities when they are faster and safer to adapt than to rebuild. Do not equate a directory, old demo, PID file, or running process with a qualified component: inspect source, contracts, dependencies, tests, and runtime behavior first.

## Known environment snapshot (reported 2026-10-19)

- Host: `SRV-DEB-05`, Debian 13; working root `/home/aiops`.
- AIOps 2.0 runtime families exist, including V8 clean deployment line, V28.3.x Command Center line, and later architecture/implementation investigations.
- Reported active services include portal, core, worker, policy, RAG, intelligence, Temporal, twin, copilot, simulator, evidence, integration, Prometheus and Grafana. Re-check live state before every deployment; this is a dated snapshot, not a current guarantee.
- Historical AIOps v1 source and evidence live under `/home/aiops/aiops-v1`.
- V145-related directories include decision intelligence, evidence fusion/matrix/acquisition/enrichment, semantic evidence engine, decision adapter, functional bridge, functional read model and decision cockpit.
- A first read-only audit was attempted on 2026-10-19. Its terminal paste/output is partially corrupted; module presence and file listings are useful leads, but the report does not qualify these modules or prove their behavior.

## Non-negotiable operating rules

1. **Protect production.** No restart, destructive cleanup, migration, config change, token rotation or production cutover without explicit scope, backup/rollback and a verified preflight.
2. **Preserve main.** Work in a dedicated branch, commit to GitHub, and open a PR. Do not claim a commit exists until GitHub confirms it.
3. **Keep evidence.** Every change must include tests run, exact outcomes, limitations, changed files, and rollback notes. Distinguish source inspection, static tests, integration tests, and live production verification.
4. **No false qualification.** Never label a demo, synthetic run, expected output, or unexecuted test as a real runtime proof.
5. **Fail closed.** Missing, stale, contradictory or unproven evidence is `UNKNOWN`; it must not be silently treated as healthy or successful.
6. **Security boundary.** Keep secrets out of Git, reports, screenshots, chat and logs. Never commit `.env`, tokens, private keys, database files or production exports.
7. **Cumulative handover.** Keep architecture, decisions, component catalog, compatibility/contracts, test evidence and release notes in the repository and update them with every significant delivery.
8. **Reuse before rebuild.** Compare historical v1/V145 code and contracts with current runtime responsibilities; adapt only where boundaries and tests can be made explicit.
9. **Do not silently fallback.** If a preferred adapter/tool is unavailable, report it and require a documented fallback decision.
10. **Do not break PC11K5 fencing guarantees.** Ownership, fencing, preconditions, effect, evidence and reconciliation invariants must remain intact.

## Required reading order for a new session

1. `README.md`
2. `docs/PROJECT-CONTINUITY.md`
3. `docs/ARCHITECTURE-AND-BOUNDARIES.md`
4. `docs/DECISION-LOG.md`
5. `docs/COMPONENT-CATALOG-AND-REUSE.md`
6. `docs/QUALIFICATION-AND-CHANGE-PROTOCOL.md`
7. Latest release notes and evidence manifests for the target version.

## Latest source review (2026-10-19)

A focused GitHub source audit is recorded in [SOURCE-AUDIT-2026-10-19.md](SOURCE-AUDIT-2026-10-19.md). The safety patch was merged via [PR #5](https://github.com/alimtalbi-ata/aiops/pull/5) at commit `493336fb51fcda41d1ece8fc1822bb13f1ef232c`: P1 escalates before evidence checks; policy no longer defaults critic validation to true and requires explicit freshness/precondition/fencing/approval inputs; the worker blocks LIVE runs before generating placeholder evidence and marks the Run BLOCKED. Added `tests/test_policy_safety.py` and `.github/workflows/quality.yml`; GitHub Actions run [39223403723](https://github.com/alimtalbi-ata/aiops/actions/runs/39223403723) passed compileall, policy unit tests and static audit. Container build, runtime qualification and synthetic E2E remain unrun. The current main branch includes this conservative guard; LIVE execution is still not qualified. Container build, runtime qualification and synthetic E2E remain unrun. A second hardening change merged via [PR #7](https://github.com/alimtalbi-ata/aiops/pull/7), commit `1bdd7235687f8b2c7081278e4dd86b8a17939ff3`: fresh installs generate random secrets, existing `.env` files are preserved, preflight rejects default secrets outside explicit demo mode, and the admin/internal tokens are checked for consistency. A third change merged via [PR #9](https://github.com/alimtalbi-ata/aiops/pull/9), commit `e6251c1ce195937b1af6019e389c9f6b3f68e2dc`: runtime credential fallbacks were removed, Compose now requires explicit secrets, the secure template is blank, and known demo values are isolated in `config/.env.demo.example`. CI run [39224781141](https://github.com/alimtalbi-ata/aiops/actions/runs/39224781141) passed Python compilation, policy tests, secret-preflight tests, static checks and `docker compose config`.

## Next work queue

- [x] Add deterministic policy safety tests and run them in GitHub Actions; preserve the run link in the source audit.
- [ ] Review and merge the LIVE safety patch only after tests pass and its diff is inspected.
- [ ] Run a corrected, truly read-only inventory of historical v1/V145 source, contracts, tests, and service ownership.
- [x] Audit and harden runtime secret fallbacks and Compose interpolation; merged via PR #9 with passing CI.
- [ ] Inspect current repository tree and deployment files; compare Git-tracked code to the host deployment without copying secrets.
- [ ] Build a reuse matrix: reuse unchanged / adapt behind adapter / replace / retire, each with evidence and owner.
- [ ] Establish one canonical incident/run/evidence/decision schema and versioned API contracts.
- [ ] Verify the complete event path from ingestion to correlation, CMDB enrichment, evidence acquisition, analysis/critic, policy gate, HITL, remediation, verification, rollback and learning.
- [ ] Test replay/simulation separately from LIVE execution, with explicit authorization and idempotency.
- [ ] Add deterministic E2E and failure-injection qualification before enabling any new live action.
- [ ] Produce cumulative deployment ZIP and updated docs/evidence for each version where a release is requested.

## Update rule

Every material change must update this record and the relevant architecture/decision/component/test documents in the same branch/PR. Add a dated entry to `docs/DECISION-LOG.md`; include commit/PR links after they exist. At session end, record exact next steps and unresolved risks here.

## Historical portal recovery update — 2026-10-19

A selective V1/V145 portal source-recovery package was created on SRV-DEB-05 without intentional runtime changes. The host reported package creation success, a 756,799-byte archive, 33 staged files and a 27,623-line V1/V145 diff. See [HISTORICAL-PORTAL-RECOVERY-RESULT-2026-10-19.md](HISTORICAL-PORTAL-RECOVERY-RESULT-2026-10-19.md) for exact paths, provenance, evidence boundaries and next steps.

The collector path defect was corrected: R33's application entry point is `app/main.py`, not `main.py` at the source root. The corrected collector completed with exit code 0. On 2026-10-19, server-side integrity checks passed: `sha256sum -c` returned `Réussi`, and `tar -tzf "$PKG" >/dev/null` completed with `TAR_READABLE=YES`. This validates the server archive against its sidecar and confirms TAR readability, but does not qualify source semantics or runtime behavior.

Next: independently recompute SHA-256 for the uploaded 15:44 archive, extract it into an isolated workspace, verify the per-file manifest, and review the R33/V1/V145 source diffs by capability. Only reviewed source/tests/docs may enter a follow-up implementation PR. Keep main protected and preserve PC11K5 fencing invariants.


## Second selective recovery package — 2026-10-19 15:44

A second selective portal source package was generated and uploaded: `AIOPS-HISTORICAL-PORTAL-SOURCE-RECOVERY-20261019-154435.tar.gz` (856,801 bytes). Its checksum sidecar states SHA-256 `829bec97028fbe21a96b8fbcc77fdb8c3092f304f5a8665106edc2c87b8180e4`; the collector reported server-side checksum validation PASS, 27,623 V1/V145 diff lines, 16,363 R33/V145 diff lines and 32 inventory rows. The current analysis runtime has not independently extracted or re-hashed the uploaded bytes, so semantic review and all build/runtime qualification remain pending. See [the recovery result record](HISTORICAL-PORTAL-RECOVERY-RESULT-2026-10-19.md). Keep changes on this PR branch, preserve `main`, and do not touch active services or PC11K5 fencing invariants.


## Continued review update — 2026-10-19 16:38 CEST

- Re-verified GitHub state: recovery PR #13 remains open, unmerged, and targets `main`; the recovery branch head was `0abcb5226457d13a13ca7a4bf353f95680b5aa41` at review time.
- Read the current `main` source for `app/portal/main.py` (blob `eac44df4abba0a3d85d69df9960cc4baa6ef71f3`). The `POST /api/demo` and `POST /api/copilot` handlers have no route-level authentication/authorization dependency in the inspected file. This is a static source finding, not proof of external reachability or exploitability.
- Opened [issue #15](https://github.com/alimtalbi-ata/aiops/issues/15) to implement a real operator authorization boundary, safe upstream errors/timeouts, request limits, CSRF/origin protections where applicable, and tests. Do not solve this by putting the internal service token in browser JavaScript or by trusting an unverified forwarded identity header.
- The uploaded 15:44 archive is still not available as a verified local byte stream in the current analysis workspace. The sidecar digest is host-reported; independent re-hash, safe extraction, manifest verification and semantic R33/V1/V145 review remain blocked. Do not claim those gates passed.
- No application code, active runtime, or PC11K5 fencing behavior was changed in this continuation. Keep PR #13 documentation-only; implement issue #15 separately after choosing and documenting the supported identity provider/reverse-proxy trust model.
- Next gates: (1) obtain the archive in a materializable attachment or provide the verified file path; (2) perform independent SHA-256 and safe TAR/member validation; (3) inspect diffs by routes, UI capabilities, schemas and dependencies; (4) implement portal authorization on a dedicated branch with tests and CI; (5) only then assess isolated UI/API/E2E qualification.
