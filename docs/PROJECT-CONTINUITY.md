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

## 2026-10-27 — P0 evidence video packaging (PR #43, in progress)

A separate `demo/evidence_video_bundle.py` now packages **only pre-existing, hash-verified operator captures** into one MP4, SRT and SHA-256 receipt. It reuses the existing PR #43 capture/verification code and selected PR #36 STAR manifest/video validation principles; it does **not** reuse synthetic STAR scenes as live evidence. Bundle requires consistent incident/run/ticket/session labels across all five captures, private outputs and ffmpeg decode verification. Offline local test: 12 tests executed including real ffmpeg render/decode from synthetic **test fixtures** (not application captures). GitHub Actions confirmation pending; no authenticated screenshots, no Debian access and no production qualification. See `docs/demo/EVIDENCE-MP4-SRT-BUNDLE-CONTRACT.md` and `docs/automation-runs/2026-10-27-2144-video-evidence.md`.

## 2026-10-28 01:43 CET — Evidence Studio visual proof gate (draft PR #43)

The five-application Playwright adapter now fails closed when the declared Run/Incident/Ticket proof is hidden, outside the captured viewport or geometrically obscured by a privacy mask. All mask targets must also be visible and in-frame, with a bounded match count. The tests include valid and negative cases; the isolated reproduction ran successfully, but the full repository suite and CI on the latest PR head remain unconfirmed. This is not pixel-level proof, operator-session authentication or LIVE capture. No Debian access, deployment or merge. Next: run repository CI, inspect browser behavior with authorized offline fixtures, resolve PR divergence by selective port rather than bulk merge.

## 2026-10-28 02:47 — P0 Evidence Studio request fence (draft PR #43)

Portage ciblé depuis PR #36 : seules les ressources `stylesheet/script/font/image/xhr/fetch` peuvent emprunter la liste GET exacte du plan de capture. Navigation document secondaire, EventSource et type absent/inconnu refusés au niveau du contexte Playwright. Test négatif pour les URL de ressources avec query, qui restent interdites par le validateur d'URL. Les tests sont ajoutés à la suite offline déjà appelée par `.github/workflows/quality.yml` sur la PR #43 ; l'exécution de la suite sur ce HEAD n'est pas confirmée et aucune preuve LIVE n'est produite. PR #43 toujours draft et non fusionnable, pas de déploiement. Voir `docs/automation-runs/2026-10-28-0247-video-evidence.md`.

## 2026-10-28 03:46 CET — P0 snapshot pinning (stacked draft PR #81)

Branche `fix/evidence-pinned-inputs-20261028-0346` créée depuis le HEAD exact
de PR #43 (`7b1664b555aaf27c7cc13fa7049d7955f46463a1`), sans modifier la
branche des autres créneaux. Le bundle MP4/SRT revalide les cinq captures
après copie par descripteur `O_NOFOLLOW` vers un staging privé, puis ne rend
que ces copies. Le changement protège la cohérence octets-vérifiés / octets-encodés
contre les modifications de fichiers sources entre vérification et FFmpeg.
Les sept tests snapshot ont réussi localement sur le module isolé (hors ligne);
la compilation Python locale a réussi. La suite du vrai dépôt, l'encodage FFmpeg
intégré et GitHub Actions sur le nouveau HEAD restent à qualifier. Pas de
capture authentifiée, pas d'accès Debian, pas de fusion, pas de LIVE.
La PR #81 est empilée sur #43 ; lorsque #43 sera stabilisée, porter ce petit
correctif vers `main` après revue et CI. Journal :
`docs/automation-runs/2026-10-28-0346-video-evidence.md`.


## 2026-10-28 04:49 Europe/Paris — Evidence Studio local byte-audit (draft PR #86)

- New independent `demo/evidence_bundle_audit.py` verifies five PNG captures, MP4/SRT SHA-256 and strict untrusted receipt structure, without network access or provenance elevation.
- Stacked on PR #81 (itself stacked on #43); source base SHA `f367175206eed07e3e7715c2057fa652d2583ac5`. No bulk PR #36 merge; reuses its STAR-style duplicate-key rejection and the existing video/capture validation contract.
- `tests/test_evidence_bundle_audit.py` covers local byte checks and negative cases (tampering, symlinks, duplicate keys, forged LIVE flags, unsafe names, missing files). Wired into the existing `quality.yml` workflow.
- This is **not** MP4 decoding, runtime session authentication, application screenshot proof, visual privacy review or LIVE qualification. No Debian access or deployment. See `docs/demo/EVIDENCE-MP4-SRT-BUNDLE-CONTRACT.md` and `docs/automation-runs/2026-10-28-0449-video-evidence.md`.


## 2026-10-28 05:44 Europe/Paris — Audit SRT canonique (draft PR #91)

Le micro-lot P0, empilé sur la PR #86 (puis #81/#43), renforce l'auditeur
hors ligne du bundle : le SRT doit correspondre exactement aux cinq libellés
canoniques et aux durées de scènes déclarées. Recalculer l'empreinte SHA-256
d'un SRT injecté ne suffit plus à le faire accepter. Tests négatifs pour
injections et durées non finies/incohérentes, avec le workflow `quality.yml`
existant. Ne pas confondre intégrité déclarative avec authentification des
sessions, vérification visuelle, attestation LIVE ou qualification du MP4.
Aucun accès Debian, déploiement, merge ou action LIVE. Consulter le journal
`docs/automation-runs/2026-10-28-0544-video-evidence.md` pour les SHA,
les résultats CI effectifs et les limites.


## 2026-10-28 06:44 Europe/Paris — Evidence Studio, liaison service/fichier

Branche dédiée empilée sur la PR #91 (puis #86/#81/#43), sans modifier les
branches des autres chantiers. Le vérificateur PNG partagé refuse les noms de
fichiers ne correspondant pas au service déclaré et les URL sources pouvant
contenir secrets, fragments, traversées ou origines non canoniques. Cela ferme
un contournement de l'auditeur : un reçu réécrit avec hash cohérent pouvait
réétiqueter une image ou injecter une URL sensible. Les tests négatifs
sont ajoutés aux suites Evidence Studio déjà référencées par `quality.yml`.

Qualification exacte, commit/PR/CI et blocages sont consignés dans
`docs/automation-runs/2026-10-28-0644-video-evidence.md`.
Aucune capture réelle, session authentifiée, revue visuelle ou déploiement
n'est impliqué. Prochain micro-lot : lier le reçu à un manifeste de capture
d'origine conservé, puis concevoir une revue de confidentialité opérateur
distincte de l'attestation runtime. Les conflits de la PR #43 avec main
restent bloquants pour la chaîne empilée.


## P0 Evidence Studio — 2026-10-28 07:44 Europe/Paris (PR empilée)

Le reçu MP4/SRT/captures référence désormais les octets du manifeste de capture
d'origine via `source_manifest_sha256`. L'auditeur hors ligne exige explicitement
le manifeste original, recalcule son SHA-256 et vérifie la cohérence des cinq
captures, IDs et provenance non attestée. Les anciens reçus sans empreinte
sont rejetés (fail-closed). La branche dédiée part du HEAD de la PR #97,
elle-même empilée sur #91/#86/#81/#43 ; aucun portage massif de #36, fusion
ou déploiement. Les résultats de tests et limites sont à consigner dans
`docs/automation-runs/2026-10-28-0744-video-evidence.md`.
La chaîne reste strictement `OPERATOR_SUPPLIED_UNATTESTED` : un SHA-256
ne constitue pas une attestation d'identité ni une revue de confidentialité.

## 2026-10-28 08:48 Europe/Paris — P0 Evidence Studio temporal session fence (draft)

- On top of PR #102 (source HEAD `2c7177a1b2dc61589bec6b132a4a30fbe7e8aaf8`), a dedicated branch changes only the shared PNG verifier, targeted regression tests and documentation. No massive merge of PR #36.
- A five-view capture set now requires nondecreasing declared UTC timestamps spanning at most 15 minutes; both video packaging and the independent receipt auditor reuse this gate. Tests cover the inclusive boundary, reversed clocks and simultaneous manifest/receipt rehashing.
- This prevents accidental cross-session assembly, **not** malicious timestamp fabrication or runtime/session attestation. Playwright operator authentication, pixel privacy review, five real services, NGX/Ollama integration and LIVE remain NOT_TESTED/BLOCKED. No Debian access, deployment or remediation.
- Use the existing `quality.yml` checks on the exact branch HEAD before merging; do not call fixtures LIVE evidence. Next: authenticated operator/session evidence and privacy review; stabilize the conflicted PR #43 chain with targeted ports.
