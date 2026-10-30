# 2026-10-29 18:20 CET — P0 : scénario ACME intégré au shell Portal

- Owner 5/5, PR unique #185 ; parent 6eb5b23e55c72c827a433e2c5788b501ebdaaf4f, stable e54c4e9a9b37e6229559a1b587c9a06b4741a8b3 non modifié.
- Réutilisation de `portal.ui_theme.shell/panel` et `portal.acme_stories.get_story("PAYMENTS_SAN")` sur la route existante `/demo-studio/business-story`. Suppression du prototype HTML autonome et de son transport ; aucun nouveau service ni workflow CI.
- Six étapes avec ancres et liens vers NOC, Core/timeline, Twin, Policy, Evidence, Demo Studio. Le récit est SIMULATED ; impact Payments, ticket GLPI, IA, HITL, preuves, effets et métriques restent UNKNOWN ou PROJECTED_ONLY tant que non attestés.
- Contrats inchangés pour Core/Twin/Policy/Evidence ; aucune API d'écriture, aucun LIVE, aucune preuve inventée. Tests `tests/test_demo_v2.py` adaptés au shell, 6 étapes, aucune requête upstream, liens et couverture deployer.
- CI `quality.yml` sur SHA final: PENDING à la création ; tests Debian, navigateur, applied.sha, rollback réel et E2E runtime: NOT_TESTED.
- P0 unique: poller Debian `deploy/poll-approved-deploy.sh` installé portal-only, incompatible avec les changements Core/Twin/Policy de la candidate. Le déployeur multi-images `deploy/deploy-acme-p0.py` existe mais n'est pas câblé au cron. READY_FOR_STABLE=BLOCKED ; inspect-host opérateur en lecture seule avant tout plan de promotion, pas de --apply sans autorisation.
