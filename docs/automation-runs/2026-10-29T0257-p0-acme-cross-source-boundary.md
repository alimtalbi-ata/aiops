# 2026-10-29 02:57 CET — P0 ACME, frontière Portal/Twin sans faux join

## Lecture préalable
- `main` `27deb9b1a66faf27df8d69b137a63451f7649d80` ; `deploy/aiops2-stable` `e54c4e9a9b37e6229559a1b587c9a06b4741a8b3` ; branche candidate #170 avant lot `37d4a210f970a8785ae26b2dbedcf378cf368407`.
- PR ouvertes consultées : #170 (Twin), #156 (Recette), #176 (Policy), #171 (NOC), #169 (UI), #153 (déployeur), #142/#148 (sources historiques). Journaux #170 du 29/10 00:04, 01:01, 01:56 et #156 consultés.
- La CI historique de #170 [#40797616879](https://github.com/alimtalbi-ata/aiops/actions/runs/40797616879) était SUCCESS (3 jobs), mais **n'atteste pas ce nouveau commit**.

## Une micro-livraison de convergence
- Source Portal canonique : `SAN-FABRIC-A` → `HOST-ESX-01` → `VM-PAY-01` → `APP-PAY-01` ; `SIMULATED_TARGET`.
- Source Twin seed : `ACME-SAN-FABRIC-A` → stockage → VM → application → service → business Payments, arêtes SQL E08/E06/E04/E02/E01 ; **aucun SAN → hôte**.
- Nouvel invariant testé contre le vrai PostgreSQL/Twin éphémères : espaces d'IDs disjoints, chemins différents, absence de liaison SAN → hôte, `runtime_impact_state=UNKNOWN`, `tenant_acl_qualified=false`. Aucun alias inventé, aucun effet LIVE.
- Contrat documentaire additif : `docs/demo/ACME-CROSS-SOURCE-BOUNDARY-V1.md` ; **aucune API modifiée**, aucun workflow ajouté. Fichier test modifié : `tests/test_twin_impact_real_integration.py`.

## Validation / release
- SHA de base : `37d4a210f970a8785ae26b2dbedcf378cf368407`. SHA du commit de ce lot : consulter le HEAD de PR #170 et le commentaire de qualification (GitHub commit généré après rédaction atomique du journal).
- **CI sur nouveau SHA : PENDING à la rédaction** ; ne pas réutiliser le succès historique. Exécuter d'abord le test Twin ciblé, puis les 3 jobs de `quality.yml`. Si CI rouge, **BLOCKED**.
- `READY_FOR_STABLE=BLOCKED`, `overall=NO_GO` même si la CI passe : le déployeur V2 ne transporte pas Twin/Core/Copilot ; pas d'ACL tenant, de Run↔Policy↔Evidence, de rollback, de preuve `applied.sha` ni de smoke Debian.
- **NOT_TESTED** : identité CMDB réelle, SAN→hôte, Payments runtime, E2E métier, tenant A/B, navigateur, Debian, déploiement et rollback. Aucune fusion, aucun push stable, aucun accès Debian ni LIVE.
- Prochain lot : Recette 5/5 #156 assemble uniquement les candidats qualifiés, vérifie la couverture de transport et les preuves terrain avant promotion ; aucun raccordement CI par simple similarité des noms.

## Résultat CI observé après commit code/tests
- **PR #170**, SHA code/tests/contrat/journal initial : `9ed4d5049c4401f7cad731a09950c8b7343425fb`.
- [GitHub Actions quality.yml #40803656719](https://github.com/alimtalbi-ata/aiops/actions/runs/40803656719) : **completed/success sur ce SHA exact**, **3/3 jobs SUCCESS** (Core/PostgreSQL/Twin, Policy/static, Grafana).
- Log du job Core réel consulté : **11/11 tests Twin** réussis, dont `test_portal_fixture_and_twin_seed_are_not_an_authenticated_join ... ok`. Les données viennent des seeds SQL + du fixture Portal et du conteneur Twin/PostgreSQL 16 éphémères, pas du serveur Debian.
- Cette mise à jour documentaire crée un nouveau HEAD : son propre `quality.yml` doit être vérifié séparément. Les succès du SHA précédent ne sont pas automatiquement transférés.
- **Contrat API inchangé ; READY_FOR_STABLE=BLOCKED / NO-GO**. Les conclusions terrain et E2E restent NOT_TESTED.
