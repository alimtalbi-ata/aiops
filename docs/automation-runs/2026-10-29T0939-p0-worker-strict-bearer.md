# P0 Worker/HITL — authentification Bearer stricte (29/10/2026, Paris)

## Relecture avant livraison
- HEAD `main` : `27deb9b1a66faf27df8d69b137a63451f7649d80` ; HEAD `deploy/aiops2-stable` : `e54c4e9a9b37e6229559a1b587c9a06b4741a8b3`. Aucun changement de ces refs.
- Candidate existante [PR #176](https://github.com/alimtalbi-ata/aiops/pull/176), branche `fix/p0-policy-synthetic-critic-fence-20261029-0235`, HEAD initial `1741a3bf4a3e27cfc7ff66eab2a40763a9b82e24`, brouillon, sans conflit. CI précédente : [PR 40837296462](https://github.com/alimtalbi-ata/aiops/actions/runs/40837296462) et [push 40837289937](https://github.com/alimtalbi-ata/aiops/actions/runs/40837289937), 3/3 SUCCESS chacun sur l'ancien SHA, **pas** sur le présent lot.
- Autres lots consultés : Recette [#156](https://github.com/alimtalbi-ata/aiops/pull/156) HEAD `aa05b435f367a01937747533ca62588668ea0c53`, Twin [#170](https://github.com/alimtalbi-ata/aiops/pull/170), NOC [#171](https://github.com/alimtalbi-ata/aiops/pull/171), UI [#169](https://github.com/alimtalbi-ata/aiops/pull/169) et [#177](https://github.com/alimtalbi-ata/aiops/pull/177), déployeur [#153](https://github.com/alimtalbi-ata/aiops/pull/153). Journaux Policy du 29/10 07:35 et 08:38 et workflow existant `quality.yml` relus. Les piles UI ne doivent pas être intégrées en bloc sans checks.
- Historique #140/#145 CI rouges ; #146 sans run PR confirmé ; #144→#147→#155→#163 déjà convergé dans main, sans cherry-pick de ce lot.

## Une livraison verticale mesurable : refus d'authentification Worker
**Défaut P0** : `POST /api/execution/start` acceptait la valeur brute du secret interne comme en-tête Authorization, sans schéma `Bearer`, car `removeprefix("Bearer ")` laissait un jeton nu inchangé. Cette ambiguïté affaiblissait le contrat d'authentification interne au point d'entrée Temporal.

**Correction** :
- `app/shared/simulation_policy_contract.py` : nouveau prédicat pur `valid_internal_bearer`, refus fail-closed des valeurs absentes, non textuelles, en-têtes nus, variantes de casse et schémas ambigus ; comparaison à temps constant du header attendu.
- `app/worker/main.py` : le point d'entrée Worker requiert strictement `Authorization: Bearer <token>` ; réponse 401 générique avant lecture Core et connexion Temporal. Aucune extension de capacité LIVE.
- `tests/test_simulation_policy_contract.py` : deux nouveaux tests, cas positif et négatifs du schéma, et garde de câblage AST de l'endpoint. Ces tests ne sont **pas** une preuve de runtime Temporal ni d'isolation tenant.
- SHA du commit code/tests : `633d5085422be397ef43a2b4668a2d57a7e8b830`. Le commit documentaire qui contient ce journal est le HEAD de la PR #176 après livraison ; consulter ce SHA et les checks finaux sur GitHub avant qualification.

## Contrats, sécurité et validation
- **Contrat interne modifié (restrictif)** : `POST /api/execution/start` refuse désormais un jeton nu (HTTP 401), même exact ; seul le header `Bearer <token>` strict est accepté pour poursuivre le préflight Core. Les clients existants utilisant `shared.http` émettent déjà le header Bearer. Aucun contrat public Core/Policy/Twin/Evidence modifié.
- Tests locaux ciblés : **NOT_TESTED** dans ce passage (environnement local sans dépendances complètes Temporal/PostgreSQL). `quality.yml` du SHA final : **PENDING à la rédaction**, ne pas recycler les résultats du HEAD antérieur. Tests de schéma et AST ajoutés au job `policy-and-static` existant, sans nouveau workflow.
- **NOT_TESTED** : HTTP Worker réel, exécution Temporal réelle, HITL authentifié, isolation tenant, provenance cryptographique Policy→Run/Evidence, E2E ACME SAN→Payments, Debian, rollback, `applied.sha`, smoke-tests post-déploiement. Aucun SSH ni déploiement.
- Observations historiques Debian fournies, non revérifiées : 7 Runs DEMO (5 BLOCKED sans gate causale démontrée, 1 RESOLVED/PASS/SIMULATE sans effet LIVE, 1 RUNNING ancien sans preuve de terminaison Temporal). Le Twin ne prouve pas l'impact Payments.
- **READY_FOR_STABLE=BLOCKED ; NO-GO E2E**. Le déployeur existant ne transporte pas automatiquement Worker/Policy/Core/Twin ; le poller seul ne qualifie aucun E2E. Aucun push `deploy/aiops2-stable`, aucune fusion, aucune mutation LIVE.

## Remise à Recette 5/5
- Conserver la PR #176 comme candidate, vérifier les 3 jobs `quality.yml` sur son SHA final et contrôler l'impact de l'authentification restrictive.
- Recette #156 seule décide de l'assemblage et de la promotion après paquet multi-services, rollback, tests de compatibilité, recette authentifiée en lecture seule et attestation Debian horodatée `applied.sha`.
- Prochain lot Policy/HITL : tester l'API Worker HTTP réelle contre Core/PostgreSQL éphémères, Temporal instrumenté sans effet, puis sandbox Temporal exécuté et liaison authentifiée Policy→Run→Evidence.

## Qualification CI de la candidate après publication
- SHA code/tests : `633d5085422be397ef43a2b4668a2d57a7e8b830` ; SHA candidate code + journal initial : `db9ff44f029d82199d014b72858b8ae898190238`.
- `quality.yml` sur **ce SHA exact `db9ff44f`** : [pull_request #40844028463](https://github.com/alimtalbi-ata/aiops/actions/runs/40844028463) **SUCCESS, 3/3 jobs** ; [push #40844021192](https://github.com/alimtalbi-ata/aiops/actions/runs/40844021192) **SUCCESS, 3/3 jobs**.
- Logs du job `policy-and-static` consultés : `test_simulation_policy_contract.py` **18/18 PASS**, y compris les deux nouveaux tests Bearer/AST. Logs `core-postgres-noc-real-integration` : **16/16** Core DEMO/Policy HTTP/PostgreSQL, **12/12** Policy HTTP, **5/5** Core NOC ; Grafana éphémère SUCCESS. Les deux tests ajoutés sont unitaires/AST, **pas** un HTTP Worker/Temporal exécuté.
- La présente mise à jour documentaire crée un nouveau HEAD ; vérifier séparément les checks de ce HEAD avant toute qualification. La CI verte ne retire aucun blocage E2E ou Debian : **READY_FOR_STABLE=BLOCKED**.
