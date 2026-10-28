# 2026-10-28 22:20–22:24 Europe/Paris — P0 NOC/Copilot Evidence binding

## Baseline et coordination
- `main` HEAD lu et revérifié avant travail: `13c455256f34e5e0f0ac55146326888b0fb84c42`. Source #161 HEAD `e4c8f3d04abff4799ae887dcf77a8eb93417743c` revérifié. Branche dédiée `feat/p0-ledger-portal-evidence-refs-20261028-2220`, empilée sur #161 → #154 → #149 → #145, sans merge massif.
- PR ouvertes, branches récentes et journaux `docs/automation-runs/` consultés; #140–#146 vérifiées (notamment #141 déjà fusionnée, #144 fermée sans fusion), #160 Core/Policy déjà intégré à main, #161 Core Evidence reste draft. Pas de modification des travaux Twin, Policy, Story ou release.
- Objectif vertical unique: ne pas montrer un AI Ledger comme sourcé lorsque le Core resolver des références Evidence manque ou refuse la liaison Run/event.

## Code, tests, contrats, commits
- `b47cc9f435488716c2f3790559657f9aae7370a4` — `app/portal/demo_ledger_read.py`: troisième GET interne Core `/api/noc/runs/{rid}/evidence-refs`, validation stricte des références et liaison exacte aux IDs Analysis; projection synthétique bornée. Viewer Bearer exigé avant toute I/O, aucune fuite du jeton interne.
- `e35dd11bfe39a2f7b5fce0b8b75f2581182c3730` — `tests/test_demo_ledger_read.py`: régression et refus sans resolver, mauvais Run, metadata tenant, payload supplémentaire, hash/time malformé, absence event, Core 401.
- `2acff7d3602c05b27aab946aa2a2382640712e7b` — `tests/test_demo_ledger_real_http.py`: Core/Portal/PostgreSQL éphémères, cas positif et nouveau négatif Ledger+Evidence sans Run event.
- `d3e2e21fe1d05f3e01d5a4ef761c76c63b8e249f` — `docs/demo/ACME-PORTAL-LEDGER-EVIDENCE-REFS-V1.md`: contrat d'intégration et compatibilité release.
- [PR draft #162](https://github.com/alimtalbi-ata/aiops/pull/162), base #161. Le commit du présent journal suit les quatre commits précédents; consulter le HEAD final dans la PR.
- Contrat viewer `aiops.demo-ledger-read.v1` conservé, mais requiert désormais Core Evidence resolver; nouveaux champs `evidence_classification=SYNTHETIC_ONLY`, `event_link_verified=true`, `evidence_refs[]` (ID, source, SHA-256, known_at). Missing/401/tenant/LIVE → 503 UNKNOWN no-store; mauvais viewer → 401 avant I/O. Ceci n'est **pas** une attestation externe ni une ACL tenant authentifiée.

## CI et vérification
- Workflow existant `.github/workflows/quality.yml` réutilisé, aucun nouveau workflow. [Run #40771395236](https://github.com/alimtalbi-ata/aiops/actions/runs/40771395236) sur SHA `d3e2e21f`: `in_progress` au moment du journal; [#40771413673](https://github.com/alimtalbi-ata/aiops/actions/runs/40771413673) PR: `queued`. **Aucun PASS revendiqué** pour le nouveau code. Plusieurs workflows hérités se déclenchent automatiquement; aucun déclenchement manuel supplémentaire.
- Dernier résultat de la base #161 [#40770614432](https://github.com/alimtalbi-ata/aiops/actions/runs/40770614432): global FAILURE (Policy safety + runtime E2E), malgré 8 tests Core/Portal/Postgres réels OK. Ces résultats ne qualifient pas cette nouvelle branche.
- Tests locaux: **NOT_TESTED**. Les tests unitaires utilisent des réponses contractuelles synthétiques; le test d'intégration prévu dans quality utilise Core/Portal/PostgreSQL réels éphémères, sans mock présenté comme E2E.

## Décision et blocages
- **NO-GO E2E / READY_FOR_STABLE: BLOCKED** jusqu'à CI verte sur SHA final, convergence #145/#149/#154/#161/#162, tests Policy/Temporal corrigés, contrats tenant et recette 5/5 qualifiés.
- Le déployeur Debian existant ne déploie pas `app/core/demo_evidence_read.py`; un Portal isolé retournerait volontairement UNKNOWN. Schedule 5/5 seul peut décider une promotion stable après couverture Core/Portal, rollback, post-deploy read-only smoke et `applied.sha` attesté. Aucun push sur stable, SSH, deploy ou LIVE.
- **NOT_TESTED**: runtime Debian, ACL tenant A/B, métriques SAN/Payments observées, causalité Twin Payments, Ollama 4B, Policy SIMULATE E2E, capture authentifiée, vidéo, rollback.
- Prochain micro-lot: requalifier la pile sur SHA unique convergé, corriger Policy/Temporal avec leur owner, puis vérifier le contrat de smoke-test Core/Portal sans secrets dans le navigateur.

## CI authentifiée et correctif — 2026-10-28 22:26 Europe/Paris
- Premier code SHA `d3e2e21fe1d05f3e01d5a4ef761c76c63b8e249f`: [quality #40771413658](https://github.com/alimtalbi-ata/aiops/actions/runs/40771413658) a exposé **2/13 tests unitaires en échec et 1/9 HTTP en échec**. Cause : le fence tenant générique rejetait le champ contractuel Core `tenant_acl_qualified=false` dans l'enveloppe du resolver. Aucun résultat PASS revendiqué sur ce SHA.
- Correctif ciblé `0da193c2ed1c42bd9bcf2527d717ffcefb572bf0` : validation stricte des sept clés de l'enveloppe et scan tenant des `items` uniquement, sans accepter un champ tenant supplémentaire.
- Sur ce **SHA de code corrigé**, [quality push #40771560841](https://github.com/alimtalbi-ata/aiops/actions/runs/40771560841) et [quality PR #40771568654](https://github.com/alimtalbi-ata/aiops/actions/runs/40771568654) : `database-migrations` **SUCCESS** avec **9/9 tests HTTP Core/Portal/PostgreSQL 16 réels**, dont source sans Run event; `quality-build-package` **FAIL** après **13/13 tests unitaires Ledger OK**, à l'étape Policy safety (**11 échecs hérités**); `runtime-e2e` **FAIL** sur Temporal synthétique; `release-kit` **SKIPPED**. `migration-runner-upgrade` et `mariadb-dr-rehearsal` **SUCCESS**. **CI globale rouge / NO-GO**.
- [V2.8 Core qualification #40771568636](https://github.com/alimtalbi-ata/aiops/actions/runs/40771568636) **FAIL** sur assertions UI historiques de registre anonyme (`test_demo_live_trace_is_source_backed`, `test_demo_run_details_are_source_backed`) incompatibles avec le garde viewer de #145; pas de contournement de sécurité.
- Tests locaux **NOT_TESTED**. Les résultats de ce paragraphe sont les jobs/logs GitHub effectivement consultés. Le présent commit documentaire ultérieur nécessite sa propre CI; ne pas extrapoler les checks du SHA code/test au SHA documentaire.
- Handoff écrit à [PR #156](https://github.com/alimtalbi-ata/aiops/pull/156) (Recette 5/5) et [#161](https://github.com/alimtalbi-ata/aiops/pull/161) (Core Evidence). **READY_FOR_STABLE=BLOCKED** ; pas de promotion ni attestation Debian.
