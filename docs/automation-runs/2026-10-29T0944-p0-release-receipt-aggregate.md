# 2026-10-29 09:44 CET — Recette 5/5 : agrégation fail-closed des reçus P0

## Inventaire GitHub réellement consulté
- HEAD `main` : `27deb9b1a66faf27df8d69b137a63451f7649d80` ; HEAD `deploy/aiops2-stable` : `e54c4e9a9b37e6229559a1b587c9a06b4741a8b3`. Aucun push/fusion stable.
- PR ouvertes et branches de livraison consultées. #153 `e5c6b030c374e47f64678f425df78cd147335eec` : quality SUCCESS (run 40819754378) ; #156 base `aa05b435f367a01937747533ca62588668ea0c53` : quality SUCCESS (40838539212).
- #170 Twin `8b5f09bd6b06b561164a694366d554794b65ac74` : quality SUCCESS (40839742751) ; #171 NOC/Evidence `d13e902dedec056370849ec33e29b8e19236ed83` : quality SUCCESS (40842391401) ; #176 Policy `12fad6c153ad252d8772870b2aa4a0c95e4df928` : quality SUCCESS (40844204566) ; #177 UI `535a689cb11f29fc3d54c409a24c39f7f6cc2ee8` : quality FAILURE (40840178897). #169 non qualifiée.
- Anciennes #140–#146 revues : #141 fusionnée (recette portail synthétique distincte), #144 fermée sans fusion ; #140/#142/#143/#145/#146 non assemblées ici. Le présent agrégateur ne duplique pas #141 : il joint les reçus transport Git, smoke Core/Twin/Copilot/Portal et Evidence Core↔Portal.
- Docs consultées : `docs/automation-runs/2026-10-29T0851-p0-offline-simulate-critic-fence.md` et contrats de #153/#156 ; scripts `check_demo_stable_coverage.py`, `check_demo_field_readonly.py`, `check_demo_evidence_receipts.py`.

## Livraison verticale — PR candidate séparée, base #156
- Branche `fix/p0-release-aggregate-receipts-20261029-0944`, issue de `aa05b43`.
- Code `98d3dff5a3473235427c501b9ab2d6d3fa80eaf7` : `scripts/check_demo_release_receipts.py` vérifie hors ligne quatre reçus explicitement fournis, sans réseau, mutation, secrets ni LIVE.
- Tests `d57b574f4e7e89ca5cadbeb44534dd813fc92c93` : ajout de cas positif NO_GO, négatifs transport non couvert, SHA incohérent, smoke non authentifié, date stale/future, run étranger, Evidence altérée, faux GO, sortie CLI sans fuite.
- Contrat additif `aiops.demo-release-receipt-aggregate.v1` : `REVIEWABLE_UNATTESTED` signifie uniquement cohérence de fichiers opérateur. `overall=NO_GO` et `ready_for_stable=BLOCKED` **constants**. Le script exige `MATCH_UNATTESTED` pour le fichier `applied.sha` mais ne le traite jamais comme attestation indépendante. Le run_id est joint uniquement entre les deux exports Evidence, jamais au smoke terrain.
- Réutilisation du step existant `quality.yml` : `test_demo_evidence_receipts.py`. Aucun nouveau workflow.
- Tests locaux : NOT_TESTED à la création de ce journal ; CI HEAD final : PENDING, à vérifier après le commit documentaire. Ne pas confondre succès CI des bases avec celui de la PR candidate.

## Recette opérateur — lecture seule et hors ligne
1. Exécuter séparément les contrôles existants sur des sources autorisées, sauvegarder les JSON : `check_demo_stable_coverage.py` (SHA stable/candidat), `check_demo_field_readonly.py` (loopback Core/Twin/Copilot/Portal et fichier applied.sha explicite), puis exporter Core Evidence refs et Portal AI Ledger avec autorisations adaptées, sans afficher de jeton.
2. Sur un hôte autorisé, exécuter `python scripts/check_demo_release_receipts.py --stable-sha <40-hex> --candidate-sha <40-hex> --run-id <RUN-DEMO> --coverage-file /abs/coverage.json --field-file /abs/field.json --ledger-file /abs/ledger.json --refs-file /abs/refs.json`. Fichiers réguliers absolus, liens symboliques finaux refusés, JSON borné et clés dupliquées refusées.
3. Archiver séparément sorties JSON horodatées, SHA approuvé, logs expurgés et preuve indépendante du déploiement si disponible. Même sortie `REVIEWABLE_UNATTESTED` = **NO_GO** ; absence de preuve indépendante = pas de promotion. L'exécution du script ne déclenche ni cron ni déploiement.

## Matrice transport / restart / tests / rollback (diff stable → #153)
| Fichier / catégorie | Copie / rebuild / restart | Tests | Rollback | Décision |
| --- | --- | --- | --- | --- |
| `app/portal/demo_v2.py`, `tests/test_demo_v2.py` (contrat déployeur ciblé) | Copie, image/container Portal prévus | Tests portail prévus, terrain NOT_TESTED | Source/Docker NOT_TESTED | REVIEWABLE seulement isolément |
| `app/policy/main.py` | Aucun transport qualifié | CI isolée | Non couvert | BLOCKED |
| `.github/workflows/quality.yml`, `promote-stable.yml` | Contrôles de release modifiés, non transportables par poller | Requalification requise | Non couvert | BLOCKED |
| `deploy/deploy-demo-studio-v2.sh`, `poll-approved-deploy.sh`, `install-approved-cron.sh` | Contrôle exécutable à requalifier | Tests CI disponibles, terrain NOT_TESTED | Non attesté | BLOCKED |
| Core / Twin / Copilot / Evidence des autres PR | Aucun transport multi-services | CI séparées, assemblage NOT_TESTED | Non couvert | BLOCKED |

Comparaison Git stable → #153 : **ahead 39, behind 0**, mais contient Policy, workflows et scripts de release. Comparaison stable → main : **diverged, ahead 43, behind 633**. Ne jamais fusionner main dans stable par force.

## Qualification GO/NO-GO
| Contrôle | État |
| --- | --- |
| Agrégateur sur fixtures CI | PENDING sur HEAD final ; tests locaux NOT_TESTED |
| CI #153, #156, #170, #171, #176 séparées | SUCCESS sur SHA cités, pas sur candidat assemblé |
| CI UI #177 | FAILURE |
| Transport/restart/rollback multi-services | BLOCKED |
| Core→Temporal→Analyst/Critic→Policy SIMULATE→Evidence→Portal, impact Payments | NOT_TESTED |
| `run_id` / `incident_id` / `evidence_ids` terrain, RBAC tenant A/B | NOT_TESTED |
| `applied.sha` authentifié, rollback Docker, smoke SRV-DEB-05 | NOT_TESTED |
| Promotion stable | **NO-GO** |

**READY_FOR_STABLE=BLOCKED.** Blocage unique : aucun candidat intégré avec déployeur multi-services/rollback qualifié. Prochain acte : assembler une fois les SHA par domaine, résoudre CI UI, requalifier transport, puis CI complète et recette terrain avec reçus indépendants. Aucun accès Debian, aucune promotion stable, aucun déploiement, aucune action LIVE.

## Clôture PR #183 — intégration limitée à la branche Recette
- PR [#183](https://github.com/alimtalbi-ata/aiops/pull/183) : HEAD candidat `a3f90736b3dedb9441d73e06daa96e883ea2ee86` (correctif import CLI `41259e51bebc63048d448d76694d9dac11407ac4`, test subprocess `a3f90736b3dedb9441d73e06daa96e883ea2ee86`).
- [quality.yml PR #40844679204](https://github.com/alimtalbi-ata/aiops/actions/runs/40844679204) et [push #40844670708](https://github.com/alimtalbi-ata/aiops/actions/runs/40844670708) : **completed/success sur ce SHA**, trois jobs SUCCESS chacun. Logs du job policy-and-static PR : **13/13 tests Evidence/agrégateur PASS**, dont 4 nouveaux tests agrégateur, et exécution subprocess sans PYTHONPATH.
- Fusion **uniquement dans la branche de développement de #156**, commit `fb658e3bc844b7b2f849c89f4dc2fb8c1cc7da04`. `main` et `deploy/aiops2-stable` inchangées. CI post-intégration sur HEAD Recette : PENDING au moment de cette mise à jour documentaire.
- Tests locaux et Debian : NOT_TESTED. Aucun reçu opérateur réel, aucun rollback, aucune attestation de déploiement. **READY_FOR_STABLE=BLOCKED, overall=NO_GO**.
