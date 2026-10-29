# 2026-10-29 01:56 CET — P0 Twin / Policy, synchronisation de quality.yml

## Périmètre et sources vérifiées
- HEAD `main` : `27deb9b1a66faf27df8d69b137a63451f7649d80` (squash de #174 : comparateur Core/Policy sans lien Run attesté).
- HEAD `deploy/aiops2-stable` : `e54c4e9a9b37e6229559a1b587c9a06b4741a8b3` ; **non modifié**.
- PR candidate unique [#170](https://github.com/alimtalbi-ata/aiops/pull/170), ancien HEAD `2318b0bcf8daaae699d7eb7e656b779033c87ce2`, ancien quality [#40791677372](https://github.com/alimtalbi-ata/aiops/actions/runs/40791677372) : completed/success, 3 jobs. Ancien succès **non transférable** au nouvel HEAD.
- Coordination consultée : #142 (sens inverse), #148 (IDs d'arêtes), #156 (recette 5/5), #171 (Ledger/Policy), #174 (fusionnée sur main), #175 (bootstrap applied.sha), #140/#141/#143/#144/#145/#146. #141 et #174 déjà fusionnées ; ne pas dupliquer.
- `main` et #170 divergeaient de 1 commit côté main / 4 côté candidate ; le changement concurrent concerne `.github/workflows/quality.yml`.

## Une livraison verticale : conserver simultanément les tests Twin et le nouveau test Policy/Core
- Commit de code `061b40a4695864c340c9c576391ec129401048cb` sur la **même** branche #170 ; aucun nouveau workflow.
- Réconcilie `quality.yml` avec le contenu du HEAD main : le test `test_core_demo_policy_real_integration.py` reste **après le démarrage du vrai service HTTP Policy**, conformément à #174.
- Préserve les migrations SQL synthétiques `003_seed_twin.sql` et `005_seed_acme.sql`, le conteneur Twin réel éphémère et `test_twin_impact_real_integration.py` dans le job Core/PostgreSQL existant.
- Contrôle statique préalable : cinq étapes requises présentes une fois chacune, et Policy démarré avant son test Core. La CI du nouvel HEAD doit encore confirmer les exécutions et l'absence de conflit.
- Contrats/API **inchangés** : `GET /api/twin/impact/{node_id}` reste read-only, interne, avec `shortest_path_edges` provenant des arêtes SQL E08/E06/E04/E02/E01. `runtime_impact_state=UNKNOWN`, `tenant_acl_qualified=false`. Le comparateur #174 garde `policy_run_binding_verified=false` ; aucune causalité Policy→Run démontrée.
- Le chemin SAN-A → stockage → VM → application → Payments est une **atteignabilité topologique SIMULATED**, pas un impact Payments réel ; aucune liaison SAN→hôte ajoutée.

## Validation et décision
- Tests ciblés historiques sur ancien SHA #170 : 10/10 Twin Docker/PostgreSQL, 8/8 Policy HTTP, 13/13 Core Policy, 5/5 Core NOC selon les logs de [#40791677372](https://github.com/alimtalbi-ata/aiops/actions/runs/40791677372). Ils ne prouvent **pas** le nouvel HEAD.
- Nouveau SHA et URL CI : **PENDING à la rédaction** ; reporter la conclusion réelle dans la conversation de PR et à #156 après lecture des jobs.
- **READY_FOR_STABLE=BLOCKED / overall=NO_GO**. Ne pas promouvoir avant qualité réellement verte sur le SHA exact, compatibilité main, recette 5/5, couverture déployeur, rollback et preuves terrain.
- **NOT_TESTED** : intégration E2E Core→IA→Policy SIMULATE→Evidence→Studio ; liaison authentifiée Policy/Run ; RBAC tenant runtime ; CMDB ; impact Payments réel ; couverture déploiement Core/Twin/Copilot ; Debian `applied.sha`, smoke-tests, rollback et navigateur client.
- Aucun accès Debian, aucun push stable, aucune remédiation LIVE ni mutation production.

## Prochain lot / handoff
Le lot 5/5 [#156](https://github.com/alimtalbi-ata/aiops/pull/156) reçoit le SHA final, le lien de la CI et la conclusion réelle. Il est seul habilité à assembler/qualifier une promotion. Ne pas considérer le poller cron comme recette E2E : le déployeur actuel transporte seulement `demo_v2.py`, `test_demo_v2.py` et l'injection `main.py`.
