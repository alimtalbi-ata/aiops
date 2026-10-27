# AIOps — quatre cycles CI décalés

Date de préparation : 2026-10-27  
Branche : `feat/v21310-star-portal-continuity-20261022`  
PR : #36 (draft)

## Cadence proposée

| Cycle | Cron UTC | Axe |
|---|---|---|
| 1 | `0 * * * *` | Contrats du portail, bootstrap et modèle d'impact ACME |
| 2 | `12 * * * *` | Cycle de vie des secrets, scripts de préflight et cohérence Compose |
| 3 | `24 * * * *` | Tests du kit cumulatif, génération d'un ZIP épinglé, intégrité et SHA-256 |
| 4 | `36 * * * *` | Gates STAR, manifeste navigateur, provenance des événements et replay |

Les quatre workflows sont indépendants, limités en permissions à `contents: read`, sans persistance de credentials checkout et sans accès aux environnements de production. Les artefacts du cycle 3 sont conservés 7 jours. Chaque workflow dispose d'un déclencheur manuel `workflow_dispatch`.

## Limites importantes

- GitHub Actions schedule utilise UTC et ne garantit pas une exécution à la minute exacte ; les runners et files d'attente peuvent retarder un cycle.
- GitHub n'exécute les événements `schedule` que depuis la branche par défaut. Les fichiers préparés dans cette branche de PR **ne seront pas actifs périodiquement avant une fusion approuvée** vers la branche par défaut. Ils peuvent être vérifiés via `workflow_dispatch` après leur présence dans une branche accessible.
- Ces workflows sont des cycles automatisés de qualification/CI ; ils ne sont pas des agents LLM qui modifient seuls le code. Les changements fonctionnels restent proposés sur la branche/PR par le processus de développement, puis validés par tests.
- Pas de fusion automatique, de déploiement, d'accès Debian, de redémarrage, d'écriture de backend, de remédiation LIVE ou de faux résultats runtime.
- Les minutes `00,12,24,36` créent trois intervalles de 12 minutes dans l'heure, puis 24 minutes entre `36` et `00` de l'heure suivante. Quatre exécutions exactement par heure ne peuvent pas former une boucle régulière de 12 minutes ; pour un intervalle constant de 12 minutes, il faut cinq déclenchements par heure (`00,12,24,36,48`).

## Workflows

- `.github/workflows/aiops-cycle-1-core-tests.yml`
- `.github/workflows/aiops-cycle-2-security.yml`
- `.github/workflows/aiops-cycle-3-candidate-kit.yml`
- `.github/workflows/aiops-cycle-4-star-evidence.yml`

Aucun résultat de test ou statut CI n'est présumé par la seule création des fichiers.
