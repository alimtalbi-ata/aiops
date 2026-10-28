# 2026-10-28 23:08 CET — P0 ACME Twin, JSON de qualification fail-closed

## Lecture initiale et concurrence
- HEAD `main` avant modification puis revérifié : `13c455256f34e5e0f0ac55146326888b0fb84c42`.
- Branche de base #159 : `64cf45b225648a153a7ef55bde90c8a61e5ea9ad`, empilée sur #157 `4f049eb9d35f7d92e8993e56d7dbca69dc8123e7`, #148 `280166ae1cf1dd475be23ab12c61102706dcdad7`, #142 `e666ce7a875ce7ee2fbdde6b7a2f35abb1f463f5`. Aucun merge massif.
- PR ouvertes et travaux des autres créneaux lus : #140, #142, #143, #145, #146, #148, #156, #157, #159, #161–#163 ; #141/#144/#160 fermées. Continuité `docs/PROJECT-CONTINUITY.md`, protocole de qualification, `quality.yml`, contrats ACME Twin et journaux récents consultés. Le motif de parsing strict est réutilisé de la PR #163, pas une copie du module Core.
- Branche dédiée `fix/p0-twin-strict-json-20261028-2303`, [PR draft #165](https://github.com/alimtalbi-ata/aiops/pull/165), base #159 ; les autres branches restent intactes.
- `deploy/aiops2-stable` vérifiée à `e54c4e9a9b37e6229559a1b587c9a06b4741a8b3`, non modifiée.

## Livraison verticale et contrat
- Commits code/tests/docs : `e758dcf190a7084e7f8e7b6a2365bf8d2d81743e` (première implémentation), `4522048548bc13c508f8c596422374782b9b117c` (correctif de test CI et borne 64 niveaux), `8688f4e2f344e71dbe869f20404364f940574c8a` (refus des flottants non finis produits par exposants).
- Fichiers : `scripts/qualify_acme_twin_readonly.py`, `tests/test_twin_impact_real_integration.py`, `docs/demo/ACME-TWIN-READONLY-QUALIFICATION-V1.md`, présent journal.
- Le qualificateur Twin refuse désormais les clés JSON dupliquées, y compris `edge_id` imbriqué ; `NaN`, `Infinity`, `-Infinity`, `1e999` ; UTF-8 invalide ; JSON tronqué et plus de 64 niveaux. Toute erreur reste `BLOCKED/NO_GO` avec un code fixe, sans exposer jeton ni corps de réponse.
- **Contrat API Twin inchangé** : `GET /api/twin/impact/{node_id}`. **Contrat de sortie CLI inchangé** : `aiops.acme-twin-readonly-qualification.v1`, `contract_status=PASS` = conformité du seed seulement ; `overall=NO_GO` même si les tests sont verts. Pas de changement des IDs ACME, de la source SQL ni des fixtures.
- Source : `db/migrations/005_seed_acme.sql`, chemin synthétique `ACME-E08 → E06 → E04 → E02 → E01` (SAN-A → stockage → VM → application → service → Payments). **Aucune arête SAN → hôte, aucun impact Payments runtime, aucun basculement SAN-B attesté.**

## CI réellement observée, y compris échec
- CI antérieure des sources #142/#148/#157/#159 : [40744150243](https://github.com/alimtalbi-ata/aiops/actions/runs/40744150243), [40760838278](https://github.com/alimtalbi-ata/aiops/actions/runs/40760838278), [40768112890](https://github.com/alimtalbi-ata/aiops/actions/runs/40768112890), [40770288142](https://github.com/alimtalbi-ata/aiops/actions/runs/40770288142), toutes `completed/success` sur leurs SHA propres, non assimilées à une recette stable.
- Premier run code [40777073943](https://github.com/alimtalbi-ata/aiops/actions/runs/40777073943) sur `e758dcf1` : **FAIL** du job Twin, car le test `too_deep` supposait à tort un rejet JSON à 1200 niveaux et le `subTest` accédait à un contexte d'exception non initialisé. Logs lus, pas de PASS revendiqué.
- Correctif [40777325668](https://github.com/alimtalbi-ata/aiops/actions/runs/40777325668) sur `45220485` : `completed/success`, trois jobs.
- **Code final avant journal** : [quality.yml #40777395304](https://github.com/alimtalbi-ata/aiops/actions/runs/40777395304), SHA `8688f4e2f344e71dbe869f20404364f940574c8a` : `completed/success`, jobs `policy-and-static`, `core-postgres-noc-real-integration`, `grafana-real-integration` tous `completed/success`. Logs du job Core/Twin lus : **9 tests Twin OK**, dont le test HTTP positif sur **vrai Twin Docker + PostgreSQL 16 éphémères** et les variantes adversariales d'octets ; Grafana réel et tests statiques également réussis.
- `quality.yml` existant réutilisé, aucun workflow ajouté. Le nom de branche `fix/**` a déclenché un run push **et** un run PR par commit (duplication non souhaitée, à éviter au prochain lot avec branche `feat/**`). Aucune action déploiement ni secret production.
- **CI du commit documentaire final** : à requalifier sur son SHA exact après publication de ce journal ; le succès ci-dessus ne lui est pas automatiquement transféré.
- Tests locaux : **NOT_TESTED**. Debian/portail client, `applied.sha`, captures authentifiées : **NOT_TESTED**.

## Décision et risques
- **GO E2E = NO-GO ; READY_FOR_STABLE = BLOCKED**. Cette PR est une qualification de parseur de données synthétiques, pas une preuve de panne Payments ou une release.
- Les ACL tenant Twin restent non qualifiées ; CMDB, corrélation runtime Core → IA → Policy SIMULATE → Evidence → Studio, HITL/Temporal, rollback et smoke-tests terrain restent **NOT_TESTED**.
- Le déployeur V2 actuel ne copie que `demo_v2.py` et `test_demo_v2.py` avec injection ciblée de `main.py` ; il ne transporte pas `app/twin/main.py` ni le qualificateur. [PR #156](https://github.com/alimtalbi-ata/aiops/pull/156) confirme ce blocage de couverture. Le poller ne valide pas E2E.
- Aucun accès Debian, aucune commande LIVE, aucune mutation de `deploy/aiops2-stable`, aucune fusion.

## Prochain micro-lot / handoff 5/5 Recette
- Remettre la pile #142 → #148 → #157 → #159 → #165, son SHA et ses CI au propriétaire 5/5 Recette (#156). Exiger la convergence sur `main`, le transport effectif Twin, un rollback testé, une recette Core/Twin/Copilot/Portal en lecture seule, l'auth/RBAC tenant et les preuves opérateur `applied.sha`/smoke-test horodatées **avant** tout GO.
- Ne pas pousser sur stable ; le lot 5/5 est seul décisionnaire de la promotion.
