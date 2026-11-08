# AIOps2 — constat Debian et plan d'exécution

Source: `ops/debian-runtime-reports:ops/debian-reports/SRV-DEB-05/latest.json`, blob `1635d38400b12c4d5ea5126a27a7db317903f1bb`, collecte `2026-11-08T15:22:01.286277+00:00`. **Constat horodaté, non preuve E2E.**

## Dépendances observées

| Service | État | Health | Image |
|---|---|---|---|
| core | running | healthy | `aiops2-core:fs1212-integrated-candidate` |
| worker | running | healthy | `aiops2-worker:fs-demo-candidate-20261105` |
| portal | running | no-healthcheck | `aiops2-portal:fs1073-csp-candidate` |
| twin | running | no-healthcheck | `aiops2-twin:fs1009-decimal-metrics-candidate-20261106` |
| policy | running | healthy | `aiops2-policy:prometheus-fix-20261104` |
| evidence | running | healthy | `aiops2-evidence:prometheus-fix-20261104` |
| intelligence | running | healthy | `aiops2-rebuild-aiops2-intelligence` |
| temporal | running | healthy | `temporalio/server:1.31.0` |
| postgres | running | healthy | `postgres:16-alpine` |
| glpi | running | no-healthcheck | `glpi/glpi:11.0.9` |

Les dépendances fonctionnelles à qualifier par test sont: événement → Core → Intelligence/Critic → Policy/HITL → Temporal/Worker → Evidence → Portal → ITSM. La topologie et les versions Docker ci-dessus ne démontrent pas la liaison fonctionnelle. Twin est optionnel en production et requis seulement pour les scénarios de qualification.

## Ordre des corrections basé sur les preuves

1. **P1 — Gate non publié**: `latest-platform.json` absent de la branche de rapports. Raccorder le script de publication au mécanisme Debian existant, sans ajouter de cron concurrent; vérifier les timestamps et le push effectif.
2. **P1 — E2E non attesté**: obtenir un reçu sur un parcours complet avec identifiants de run, statuts Policy, activité Temporal, evidence et état Portal. Ne pas contourner le HITL ni créer de ticket GLPI en doublon.
3. **P1 — Déploiement non attesté**: vérifier le contenu de `poll.sh`, sa branche autorisée, les journaux et un reçu image/commit/rollback.
4. **P2 — Healthchecks absents**: Portal, Twin, GLPI sont `running` sans healthcheck Docker. Ajouter des probes applicatives après validation de leurs routes et politiques d'authentification.
5. **P2 — Packaging client**: tester une installation reproductible sans Twin et avec adaptateurs interchangeables.

## Livrables code

- `scripts/ops/platform_gap_analyzer.py` : classification déterministe des écarts à partir des rapports JSON.
- `tests/ops/test_platform_gap_analyzer.py` : cinq tests de contrats hors ligne.
- `.github/workflows/aiops2-reconciliation-audit.yml` : CI mise à jour.

**Statuts:** CODE=COMMITTED; CI=NOT_VERIFIED; DEBIAN=NOT_INSTALLED; E2E=NOT_VERIFIED. Aucune livraison runtime ne peut être déclarée sur cette seule base.
