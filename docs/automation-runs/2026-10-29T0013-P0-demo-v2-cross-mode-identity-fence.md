# 2026-10-29 00:13–00:15 CET — Release P0 UI, collisions Core LIVE/DEMO

## Départ et coordination
- `main` HEAD vérifié avant écriture : `103c1ded7bd39daf59699a4e416fc3f91dc74d57` ; `deploy/aiops2-stable` : `e54c4e9a9b37e6229559a1b587c9a06b4741a8b3` (inchangée).
- Branche exclusive existante `release/p0-demo-v2-ui-candidate-20261029-0004` / [PR draft #169](https://github.com/alimtalbi-ata/aiops/pull/169), SHA de départ `8ef56f757b44f7ccfb5388befbd7524177409a3b`. Ascendance UI #140 → #150 → #152 → #158 → #166 → #169 ; aucun merge massif.
- PR et créneaux consultés : Recette #153/#156, Twin #142/#170, NOC #145/#171, Core/Policy #163 et journaux `docs/automation-runs/2026-10-29T0004-p0-policy-release-convergence.md`, `docs/PROJECT-CONTINUITY.md`, `quality.yml`, journal UI #169. Aucun fichier des autres owners modifié.

## Micro-correctif P0 : inventaire Core ambigu
- `app/portal/main.py` : `_unique_demo_run` compte maintenant **toutes** les entrées Core avec le `run_id` demandé, y compris `LIVE`, **avant** de filtrer les modes DEMO/REPLAY/STORY. Une collision LIVE/DEMO n'est pas un run démontrable unique ; refus HTTP 404 avant détail, ai-ledger, gates et Evidence. Un unique run LIVE reste refusé. Aucun endpoint ni schéma canonique changé.
- `tests/test_v28_portal_ui.py` : test négatif avec deux ordres LIVE/DEMO et vérification des deux routes (SSR et polling), de l'absence d'I/O vers les détails/registries et du code 404. Les tests positifs de tenant cohérent déjà présents restent en place.
- Commits : `79181fd771c2782d2986ce8113a4f7d33cb790b5` (code) ; `f24ee04277074502fef650ddb75150a0b37b8e57` (test). Le présent journal est un troisième commit documentaire.
- Contrat visible : `/demo-studio/run/{rid}` et `/api/demo-status/{rid}` conservent les routes ; une collision d'identité inter-modes est désormais `404 demo_run_not_found`. Aucun fallback LIVE, aucune assertion de preuve Payments ou E2E.

## CI et limites observées
- Workflow existant `.github/workflows/quality.yml` réutilisé via déclenchement GitHub automatique, sans dispatch manuel. [quality.yml sur SHA tests f24ee04](https://github.com/alimtalbi-ata/aiops/actions/runs/40785899112) **IN_PROGRESS** au contrôle initial, pas de PASS revendiqué.
- [CI précédente du candidat #169](https://github.com/alimtalbi-ata/aiops/actions/runs/40785064384) : **completed/failure**, job `quality-build-package` (Policy safety) et `runtime-e2e` en échec ; ne pas masquer ni contourner les garde-fous.
- Tests locaux du dépôt : **NOT_TESTED** (clone GitHub impossible : résolution DNS indisponible). Résultats du nouveau test sur le SHA final : **PENDING** tant que les logs ne sont pas vérifiés. Navigateurs authentifiés, isolation tenant runtime, Core/Twin/Copilot/Policy/Evidence réels assemblés, recette Debian et `applied.sha` : **NOT_TESTED**.
- Déployeur de #153 transporte `demo_v2.py` et `test_demo_v2.py` et injecte un fragment de `main.py` : **ne transporte pas** les fonctions `_unique_demo_run` et `_demo_detail_matches`. Le paquet UI reste **BLOCKED** jusqu'à couverture et rollback validés par Recette 5/5.

## Décision et remise
- **NO-GO / READY_FOR_STABLE=false.** Pas de fusion, push stable, SSH, déploiement Debian, remédiation LIVE ni lecture de secrets.
- À Recette #156 : considérer SHA unique de cette PR après journal et CI ; ne pas promouvoir tant que Policy/runtime-e2e, déployeur, rollback, smoke-tests et `applied.sha` ne sont pas qualifiés. L'inventaire de Core ne prouve pas à lui seul une ACL tenant.
- Prochain micro-lot : qualifier ce candidat contre Core/PostgreSQL et navigateur éphémères, puis fournir un paquet complet de fichiers `main.py` et `demo_v2.py` au responsable Recette sans modifier stable.
