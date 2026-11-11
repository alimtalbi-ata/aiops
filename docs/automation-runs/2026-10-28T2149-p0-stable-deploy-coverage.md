# 2026-10-28 21:49–21:53 Europe/Paris — Recette 5/5, couverture de déploiement stable

## État initial vérifié
- HEAD `main` avant chaque modification : `ec05c89e92a6611922dccbe3690ce1476e3aec92`.
- HEAD `deploy/aiops2-stable` : `e54c4e9a9b37e6229559a1b587c9a06b4741a8b3`. Comparaison GitHub : **diverged**, 39 commits ahead côté main, 633 behind côté stable ; aucune promotion fast-forward possible depuis main.
- PR consultées : #140, #141 (fusionnée), #142, #143, #144, #145, #146, #147, #148, #149, #150, #151 (fusionnée), #152, #153, #154, #155. #146 est conflictuelle ; #140/#145/#152/#154 ont des checks en échec sur leur SHA. #142/#144/#143/#153 et #155 disposent de checks verts à leur SHA, sans prouver la compatibilité interbranches ni le runtime.
- Branches de livraison, `docs/PROJECT-CONTINUITY.md`, `docs/QUALIFICATION-AND-CHANGE-PROTOCOL.md`, dernier journal E2E `2026-10-28T2110-p1-acme-aggregate-source-fence.md`, `quality.yml`, déployeur et poller de #153 consultés.
- Le déployeur de #153 copie `app/portal/demo_v2.py` et `tests/test_demo_v2.py`, injecte seulement un fragment dans `app/portal/main.py`, puis reconstruit uniquement le portail. Il ne transporte **pas** Core/Twin/Copilot/Temporal/Policy/Evidence. Le poller ne constitue pas une recette E2E.

## Micro-livraison et contrat
- Branche : `fix/p0-stable-deploy-coverage-20261028-2149`, créée depuis le SHA exact de main.
- PR draft : [#156](https://github.com/alimtalbi-ata/aiops/pull/156) vers `main` (pas vers stable).
- Commits code/tests/CI : `9867da507007fd2e8f898947d864a04ab045f8ed`, `43dbe81e3cfb4b0ab06394df6609edf0045dd9a2`, `10b4d3559f9a4589c525771836f3473a6783867a`.
- Fichiers : `scripts/check_demo_stable_coverage.py` (nouveau), `tests/test_demo_stable_coverage.py` (nouveau), `.github/workflows/quality.yml` (réutilisé, une étape de tests ajoutée), présent journal.
- Contrat **nouveau** `aiops.demo-stable-deployment-coverage.v1` : entrée = deux SHA de commits locaux et dépôt Git local ; sortie JSON `assessment=READY_FOR_REVIEW|BLOCKED`, `overall=NO_GO`, provenance `OFFLINE_GIT_DIFF_NOT_RUNTIME`, chemins non couverts et tests terrain `NOT_TESTED`. Le script n'utilise ni réseau, ni token, ni déploiement.
- Vérifie l'ascendance fast-forward, la présence du module et du déployeur, le diff Git réel et la liste de fichiers transportés. Rejette notamment toute modification `app/core/**`, `app/twin/**`, `app/copilot/**`, `app/portal/main.py`, `db/**` et `compose.yml` avec ce déployeur limité. `READY_FOR_REVIEW` **n'est jamais** un GO.
- Invocation future, uniquement dans un clone local autorisé contenant les deux commits : `python3 scripts/check_demo_stable_coverage.py --repo . --stable-sha <SHA_40_STABLE> --candidate-sha <SHA_40_CANDIDAT>`. Ne pas invoquer automatiquement le poller ni modifier stable.

## Tests et CI
- Tests locaux réellement exécutés : `PYTHONPATH=/mnt/data/aiops_stable_gate python -m unittest discover -s /mnt/data/aiops_stable_gate/tests -p test_demo_stable_coverage.py -v` ; **7/7 OK**, dépôt Git temporaire réel, aucune requête réseau. Vérifient changement autorisé, Core non transporté, `portal/main.py` injecté, suppression, divergence, SHA invalide/no-op, Twin/SQL non transportés.
- CI existante `quality.yml` déclenchée sur SHA code `10b4d3559f9a4589c525771836f3473a6783867a` : [push #40767066171](https://github.com/alimtalbi-ata/aiops/actions/runs/40767066171) **in_progress** et [PR #40767095456](https://github.com/alimtalbi-ata/aiops/actions/runs/40767095456) **queued** lors de la rédaction. Ne pas déclarer PASS avant les conclusions GitHub vérifiées. Après le commit de journal, vérifier aussi les checks du HEAD final.
- Tests réels Core/PostgreSQL et Grafana de quality.yml : **PENDING** pour cette PR, pas des tests ACME inter-composants. Tests terrain Debian, applied.sha, rollback effectif et captures authentifiées : **NOT_TESTED**.

## Matrice de décision (priorisée)
| Priorité | Critère | État |
| --- | --- | --- |
| P0 | Fast-forward main vers stable | **BLOCKED** : histoires divergentes |
| P0 | Couverture déployeur Core/Twin/Copilot/Policy/Evidence | **BLOCKED** : seuls fichiers Studio copiés |
| P0 | CI de toutes les PR candidates combinées | **BLOCKED** : #140/#145/#152/#154 rouges ; combinaison non testée |
| P0 | Recette Core→Temporal→Analyst/Critic→Policy SIMULATE→Evidence→Portal, IDs authentifiés | **NOT_TESTED** |
| P0 | Reçu terrain `applied.sha`, smoke-tests, rollback vérifié | **NOT_TESTED** |
| P0 | Impact Payments observé (vs chemin Twin déclaré) | **NO_GO** |
| P1 | Parcours client vidéo / captures opérateur | **NO_GO** |

## Risques et prochaine action
- **Décision : BLOCKED / NO_GO.** Aucune promotion sur `deploy/aiops2-stable`, aucune commande LIVE ni accès Debian.
- Réconcilier la lignée stable par une PR de promotion examinée, **pas** un reset/force-push ; modifier le déployeur pour transporter effectivement tous les composants nécessaires, avec rollback par composant et tests sur services éphémères.
- Exiger un script post-déploiement en lecture seule avec authentification locale, horodatage et résultats redigés par l'opérateur, distinct du poller ; récupérer `applied.sha` et preuve smoke réelle avant GO.
- À la prochaine exécution : qualifier la convergence #142/#144/#143/#153 et les PR dépendantes sur un SHA candidat unique, puis exécuter le préflight offline et corriger les blocages un à un.
