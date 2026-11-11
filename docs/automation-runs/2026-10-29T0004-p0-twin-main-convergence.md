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
- CI candidate `quality.yml` sur commit code/tests/docs `8cc47c7480c717b444d044cc4ff71f2d471f98bb` : [run 40784993317](https://github.com/alimtalbi-ata/aiops/actions/runs/40784993317) **completed/success**, trois jobs SUCCESS, logs réellement consultés. Le job Core/PostgreSQL 16 + Twin Docker réel a exécuté **10/10 tests Twin**, **11/11 tests Core Policy DEMO** et **5/5 tests Core NOC**, tous OK. Le job policy-and-static (incluant navigateur Chromium éphémère, audit statique et Policy) et le job Grafana réel sont SUCCESS. Les cas HTTP adversariaux modifiés en mémoire restent des tests négatifs unitaires, pas des serveurs réels. Le présent commit documentaire doit être revérifié sur son propre SHA ; ne pas transférer automatiquement le PASS du code. Aucun workflow parallèle.
- Tests locaux, Debian, applied.sha, navigateur client, CMDB, ACL tenant et chaîne Core→IA→Policy SIMULATE→Evidence→Studio : **NOT_TESTED**. Aucune preuve LIVE.
- **READY_FOR_STABLE=BLOCKED / E2E=NO-GO**. Le déployeur V2 (#153) ne transporte pas Twin ; #156 doit qualifier couverture/rollback et recette. Stable diverge de main, protections à respecter. Pas de promotion, merge, accès Debian ou commande LIVE.
- PR candidate : [#170](https://github.com/alimtalbi-ata/aiops/pull/170) (draft vers main), base initiale `13c455256f34e5e0f0ac55146326888b0fb84c42`, sans conflit constaté lors de l'ouverture. Le portage conserve la vérification Core Policy de main.
- Prochain lot : remettre SHA final et checks à #156 pour assemblage 5/5 et qualification du transport Twin + rollback ; exiger smoke-tests opérateur et applied.sha authentifié avant GO.
