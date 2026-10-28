# 2026-10-29 00:04 CET — Candidate P0 ACME Twin sur main

## Départ et coordination
- HEAD main vérifié immédiatement avant branche : `13c455256f34e5e0f0ac55146326888b0fb84c42` ; stable `e54c4e9a9b37e6229559a1b587c9a06b4741a8b3`, non modifiée.
- PR ouvertes examinées : #140, #142, #143, #145, #146, #148, #156, #157, #159, #165, #168. #141 fusionnée, #144 fermée/portée par #160. Les journaux de #156 et #168 et `docs/PROJECT-CONTINUITY.md` ont été lus.
- Sources ciblées : #142 (direction inverse), #148 (arêtes DB), #157 (sonde read-only), #159/#165/#168 (refus proxy/JSON/HTTP). Source vérifiée `70ae1329633d37c8dd0bc8c1dedea3a3209c8137`, CI historique [40784408061](https://github.com/alimtalbi-ata/aiops/actions/runs/40784408061) completed/success sur **ce SHA source**, pas sur la candidate.
- Branche propre `feat/p0-acme-twin-main-candidate-20261029-0004` créée à partir de main ; aucun merge massif, aucune modification des branches des autres créneaux.

## Livraison verticale et contrat
- Port ciblé de `app/twin/main.py`, `tests/test_twin_impact_real_integration.py`, `scripts/qualify_acme_twin_readonly.py`, des deux contrats `docs/demo/ACME-TWIN-*.md` et des seules étapes Twin dans `.github/workflows/quality.yml`. La vérification Core Policy de main est conservée.
- `GET /api/twin/impact/{node_id}` : reverse traversal sur dépendances existantes, `shortest_path_edges` issus de la même transaction PostgreSQL read-only, refus 401 anonyme. Contrat additif `root/affected`, provenance `TWIN_DB_TOPOLOGY_READ_ONLY`, `runtime_impact_state=UNKNOWN`, `tenant_acl_qualified=false`, `live_remediation_authorized=false`.
- Source de données : `db/migrations/005_seed_acme.sql` déjà sur main, arêtes E08→E06→E04→E02→E01, SAN-A→stockage→VM→application→service→Payments. **Aucune arête SAN→hôte**. `ACME-E10` VM→hôte est indépendante. Pas de causalité/panne Payments prouvée.
- Correction documentaire : la sonde valide 10 candidats et 10 arêtes attendues, **pas** les 25 nœuds/23 arêtes à elle seule ; cette couverture relève du test DB CI.

## Validation et décision
- CI candidate `quality.yml` : **PENDING** à la création du commit ; vérifier le run associé au SHA final avant tout PASS. Les tests ciblés Twin sur vrai conteneur/PostgreSQL éphémères et les tests Core Policy main sont conservés dans le workflow. Aucun workflow parallèle.
- Tests locaux, Debian, applied.sha, navigateur client, CMDB, ACL tenant et chaîne Core→IA→Policy SIMULATE→Evidence→Studio : **NOT_TESTED**. Aucune preuve LIVE.
- **READY_FOR_STABLE=BLOCKED / E2E=NO-GO**. Le déployeur V2 (#153) ne transporte pas Twin ; #156 doit qualifier couverture/rollback et recette. Stable diverge de main, protections à respecter. Pas de promotion, merge, accès Debian ou commande LIVE.
- Prochain lot : confirmer checks du SHA candidate, remettre à #156 pour assemblage 5/5 et qualification du transport Twin + rollback ; exiger smoke-tests opérateur et applied.sha authentifié avant GO.
