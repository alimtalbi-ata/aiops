# 2026-10-29 03:34 Europe/Paris — P0 Policy : assertions typées strictes, aucun effet réel

## État et coordination
- Lecture GitHub : `main` `27deb9b1a66faf27df8d69b137a63451f7649d80`, `deploy/aiops2-stable` `e54c4e9a9b37e6229559a1b587c9a06b4741a8b3` (non modifiés). Branche/PR existante [#176](https://github.com/alimtalbi-ata/aiops/pull/176), HEAD initial `064854a7f56e50a10ebf25d6ccb1bae2848e3681`. Pas de nouvelle PR ni de workflow.
- PR de convergence : #144/#147/#155 via #160, #163, #173 et #174 intégrées dans main ; #176 correction Policy synthétique en attente. Autres créneaux : #169/#177 UI, #170 Twin, #171 NOC/Evidence, #153 déployeur, #156 Recette. Aucune intégration concurrente ni promotion stable.
- Journaux consultés : `2026-10-29T0004-p0-policy-release-convergence.md`, `2026-10-29T0033-p0-policy-real-http-ci.md`, `2026-10-29T0144-p0-policy-core-unbound-crosscheck.md`, `2026-10-29T0235-p0-policy-synthetic-critic-fence.md`.

## UNE livraison verticale
- Défaut P0 reproductible dans le modèle Pydantic précédent : `critic_validated="yes"`, `redundancy_ok="true"`, `human_approved="true"`, `evidence_count="2"` et `confidence="0.99"` étaient coercibles en assertions positives. Une décision synthétique `PASS/SIMULATE` pouvait ainsi reposer sur des types non conformes.
- `app/policy/main.py` : `StrictBool` pour six indicateurs de sécurité, `StrictInt` pour le nombre de preuves, `StrictFloat` pour la confiance. Les payloads mal typés sont refusés par HTTP 422 avant `evaluate`. Les booléens JSON et nombres JSON correctement typés restent acceptés. `PASS/SIMULATE` n'autorise aucune mutation.
- `tests/test_policy_safety.py` et `tests/test_policy_real_http_integration.py` : cas négatifs couvrant chaque indicateur, le count et la confiance, et cas positif DEMO SIMULATE. Les suites sont déjà lancées dans `.github/workflows/quality.yml` (pas de CI ajoutée).

## Contrat, vérification et limites
- `POST /api/policy/check` : même route et même schéma de réponse ; changement **restrictif du contrat d'entrée** : rejet HTTP 422 des booléens/nombres transmis en chaînes et des nombres booléens. `StrictFloat` accepte les nombres JSON entiers valides (ex. 1), pas les chaînes. Le worker doit fournir des types JSON natifs.
- Code/tests + journal SHA `33022e0aff199274fb8dca3e73b9af52dd5d69f2` : [quality.yml PR #40807245718](https://github.com/alimtalbi-ata/aiops/actions/runs/40807245718) et [push #40807239352](https://github.com/alimtalbi-ata/aiops/actions/runs/40807239352), **completed/success, 3/3 jobs chacun** sur ce SHA. Logs consultés : **18/18** Policy unitaires (dont tests des types), **11/11** Policy HTTP réel (dont refus de types), **14/14** Core/Policy/PostgreSQL 16 ; Grafana réel PASS. Tests locaux : NOT_TESTED. Après le présent commit documentaire, requalifier le nouveau HEAD exact ; ne pas confondre CI du parent et CI finale.
- Les assertions typées restent **non attestées** : aucune identité Critic/Run/Incident/HITL authentifiée, aucune provenance Evidence ni isolation tenant A/B démontrée. Le comparateur Policy/Core reste NO_GO. Temporal, rollback, postchecks, métriques SAN→Payments, Debian et `applied.sha` : NOT_TESTED.
- États Core rapportés non revérifiés : 5 BLOCKED sans gate ne prouvent pas la cause ; 1 RESOLVED/PASS/SIMULATE ne prouve aucune remédiation LIVE ; 1 RUNNING ancien ne prouve pas de terminaison Temporal.
- **NO-GO E2E ; READY_FOR_STABLE=BLOCKED.** Le déployeur V2 n'embarque pas Policy. Aucun push sur `deploy/aiops2-stable`, aucune fusion, aucun SSH Debian, aucun effet LIVE.

## Remise et prochain lot
- Remettre SHA exact, checks de `quality.yml`, contrat d'entrée et blocages à Recette 5/5 [#156](https://github.com/alimtalbi-ata/aiops/pull/156) après observation de la CI.
- Prochain lot : assembler les candidats sans duplication, vérifier la compatibilité du worker JSON, l'authentification et la liaison Policy→Run/Evidence, le rollback et les smoke-tests Debian avant tout GO.
