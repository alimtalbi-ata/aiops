# 2026-10-29 00:07 Europe/Paris — Recette 5/5, garde de couverture avant poller

## SHA et coordination
- HEAD `main` observé avant modification : `13c455256f34e5e0f0ac55146326888b0fb84c42`.
- HEAD `deploy/aiops2-stable` observé : `e54c4e9a9b37e6229559a1b587c9a06b4741a8b3`, branche protégée, **non modifiée**. Comparaison : divergence 40 ahead / 633 behind, pas de fast-forward `main` → stable.
- #153 (déployeur/poller) HEAD `34c4364176b0dd33784162a117072d9abdc6e96b`, CI antérieure verte, base `feat/demo-studio-v2-delivery-20261028` ; #156 (recette/coverage) HEAD `5fb1a4f3a51fde8b175c9dabd3010f7e8fa89960`, CI antérieure verte. Revue des PR ouvertes et travaux Core/Policy #163, Twin #165/#168, UI #166, Evidence #167. Ces checks propres ne qualifient pas leur assemblage.
- Branche dédiée empilée sur #153 : `fix/p0-poller-undeployed-change-fence-20261029-0006`. Aucun push direct sur stable, main ou les branches des autres créneaux.

## Micro-livraison verticale
- `deploy/poll-approved-deploy.sh` : refuse le bootstrap si `applied.sha` est absent/malformé ; vérifie ascendance et **diff réel Git en NUL** avant checkout et avant toute invocation du déployeur. Seuls les deux fichiers copiés par le déployeur V2 et les fichiers de métadonnées/tests/docs sont acceptés. Refuse notamment Core/Twin/Copilot, migrations, `portal/main.py` et toute modification du déployeur/poller ; refuse suppressions, types et chemins anormaux. La mise à jour d'un déployeur exige désormais une qualification et une intervention distinctes, pas un déploiement automatique.
- `tests/test_poll_approved_deploy.py` : conserve les tests Git offline existants et ajoute refus de bootstrap sans SHA, modification Core, modification déployeur et suppression du module déployé ; les cas positifs portent désormais sur le module effectivement copié.
- Contrat : **poller auto-deploy V2 = uniquement `app/portal/demo_v2.py` et `tests/test_demo_v2.py` copiés ; `portal/main.py` est injecté par ancre, pas transporté**. Aucune évolution d'API, DEMO/LIVE ou RBAC.
- Matrice de transport : `demo_v2.py` → copie + tests portail + rebuild/restart portail + rollback sources/conteneur ; `test_demo_v2.py` → copie + test ; `portal/main.py` → ancre seulement, changement complet BLOCKED ; `app/core/**`, `app/twin/**`, `app/copilot/**`, `app/policy/**`, `app/worker/**`, `db/**` → **non copiés, non redémarrés, non restaurés : BLOCKED**. `deploy/**` → changement de déployeur **BLOCKED** en mode automatique.
- Commits code/tests : `39380882ace1ef75ea35c82c2ed031c51bcf3b2e`, `38786d3ccb5fc7e5322e73d260414c820986e0d8`.

## Validation, limites et décision
- Les tests sont **NOT_TESTED à la rédaction de ce journal** ; exécuter le job existant `quality.yml` sur le HEAD final de la PR et consigner l'URL/conclusion dans la PR après confirmation. Ne pas annoncer PASS avant les logs.
- Les fixtures Git locales du poller sont des tests de contrat **offline**, pas une qualification de déploiement Docker ni un E2E inter-services.
- `applied.sha` réel, Docker rollback terrain, tenant RBAC, Core→Temporal→Analyst/Critic→Policy→Evidence→Portal, corrélation IDs, impact Payments, captures authentifiées : **NOT_TESTED**.
- **READY_FOR_STABLE=BLOCKED ; overall=NO_GO** : historiques divergents, déployeur portail seulement, pas de recette terrain attestée. Aucun accès Debian, déploiement, fusion stable ni effet LIVE.

## Prochain acte
Vérifier la CI sur SHA final, puis faire porter ce garde-fou à #153 uniquement après checks verts ; réconcilier le déployeur multi-modules et la recette terrain avant toute PR de promotion. Ne jamais fusionner `main` de force dans stable.

## CI initiale et correctif dans le même micro-lot
- HEAD initial `81056b766ff5f542efc8ae650b54c3c60f531444` : [quality.yml PR #40785095757](https://github.com/alimtalbi-ata/aiops/actions/runs/40785095757), échec réel du step `Approved poller and Docker rollback-name contract (offline)` : **5 tests échoués sur 9**, erreur de syntaxe Bash ligne 63 dans le garde des chemins ; logs du job `123156168904` consultés. Ne pas compter ce run comme PASS.
- Correctif `e3781bb2b659567d0e27e082262e6ed680ca2636` : reconstruit le fichier depuis la version #153 et utilise `[[ "$path" =~ [[:cntrl:]] ]]` au lieu d'une expression de contrôle mal échappée. Vérification locale limitée de syntaxe de la condition via `bash -n` : PASS ; **suite Git complète à requalifier en CI sur HEAD final**.
- Pendant le passage, `main` a avancé à `103c1ded7bd39daf59699a4e416fc3f91dc74d57` par fusion ciblée de #163 Core/Policy ; ne modifie pas la décision stable.
