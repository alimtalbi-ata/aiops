# Automation P1 ACME / ITSM — 2026-10-28 04:32–04:39 Europe/Paris

## Base vérifiée
- `main` lu avant modification : `1ed749129e32ea9a8854c437c7de9a6a8b43e35b`.
- PR #36, #37, #39, #41, #43 inspectées (métadonnées et liste ciblée des fichiers #36) ; continuité `docs/PROJECT-CONTINUITY.md`, architecture, stratégie de tests, README et workflow `quality.yml` lus.
- Base ciblée de la PR #80 : `cf935bb32ea4492e35e29d2af6512cb3c6f1b2cc` ; pas de fusion massive. La PR #80 apporte la barrière d'écriture DEMO et le lien au fixture.
- Nouvelle branche `feat/p1-acme-run-readback-20261028-0432`, PR draft [#85](https://github.com/alimtalbi-ata/aiops/pull/85), **empilée sur #80**.

## Code, tests, documentation
- `app/portal/acme_run_readback.py` : GET protégé par `AIOPS_PORTAL_READ_TOKEN`, Core GET interne existant, validation stricte du Run DEMO et des identifiants fixture, réponse `MATCHED_UNATTESTED` ou `UNKNOWN`, ticket GLPI `null`, jamais d'action LIVE.
- `app/portal/main.py` : montage de route et formulaire de lecture Golden DEMO avec jeton opérateur distinct, effacé immédiatement, sans persistance.
- `tests/test_acme_run_readback.py` : déterminisme, identité, mode LIVE/REPLAY/STORY, version/statut invalides, fixture altéré, RBAC avant I/O, erreur Core expurgée, aucune fausse preuve GLPI, intégration visuelle de la route et du formulaire.
- `.github/workflows/quality.yml` : ajout du test au job existant, sans nouvelle CI parallèle.
- `docs/demo/ACME-GOLDEN-RUN-READBACK-20261028.md`, `docs/PROJECT-CONTINUITY.md` : contrat et limites.

Commits de travail (avant ce journal) : `0c521c9`, `81ad44e`, `2a45610`, `f2b8714`, `633dd91`, `3da5441`, `f6b2475`, `601fef4`, `b7c3671`, `be65657`.

## Validation réellement observée
- [GitHub Actions 40627534615](https://github.com/alimtalbi-ata/aiops/actions/runs/40627534615) : `completed/success` sur `f6b2475` (avant ajout du formulaire UI).
- [GitHub Actions 40627581962](https://github.com/alimtalbi-ata/aiops/actions/runs/40627581962) : `completed/success` sur `601fef4` (formulaire UI inclus, avant son test de présence).
- [GitHub Actions 40627591935](https://github.com/alimtalbi-ata/aiops/actions/runs/40627591935) : en cours au moment du journal (test UI inclus).
- [GitHub Actions 40627605337](https://github.com/alimtalbi-ata/aiops/actions/runs/40627605337) : en cours au moment du journal (documentation incluse).
- Tests locaux complets : **NOT_TESTED** (aucun checkout complet local accessible). L'exécution CI n'est pas un test d'intégration Core/Temporal/GLPI.

## Risques, blocages et prochain micro-lot
- PR #85 dépend de #80 ; rebaser/retargeter seulement après intégration de #80, résoudre les conflits potentiels sur `main.py` et `quality.yml`.
- Le GET Core ne constitue pas une attestation d'exécution Temporal, ni une preuve de capture réelle ; la corrélation GLPI reste `UNKNOWN`. Aucun service GLPI éphémère, Core/Temporal E2E ou NGX n'a été qualifié ici : **NOT_TESTED**.
- Prochain micro-lot : vraie intégration éphémère Core/PostgreSQL/Temporal et GLPI, vérifier séparément les IDs, puis un lien GLPI issu d'une preuve d'association canonique ; ne jamais promouvoir une observation isolée.
- Aucun accès Debian, aucune action LIVE, aucun déploiement, aucune fusion.
