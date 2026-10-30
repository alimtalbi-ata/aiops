# 2026-10-29 18:16 CET — P0 Portail : point d'entrée business ACME

- Owner: 2/5 Portail. PR existante **#185** (pas de nouvelle PR), parent vérifié `9eb1c4d7df3b5b037dd406d1aae673fb0351d069`. Intégration atomique, SHA résultant à lire sur HEAD #185 et sur le handoff 5/5.
- Source réutilisée **sans réécriture** : `docs/demo/acme-business-story.html` sur `prep/acme-demo-offline-20261029`, commit `ea7440e60200416c3219c9023e3054b9d6ccebb4`, blob `f37f2bdcc5e8db52e811c105fb7a11816c3fd880`. Copie bit à bit dans `app/portal/acme_business_story.html`.
- Route read-only `GET /demo-studio/business-story`, liens sur `/` et `/demo-studio`. Présentation autonome six écrans, HTML/CSS/JS inline, aucune API appelée et aucune action LIVE. Ne pas la confondre avec une preuve SAN→Payments, Core, HITL, Evidence ou gain mesuré.
- Transport: Dockerfile Portal existant `COPY portal /app/portal` embarque le HTML. `deploy/deploy-acme-p0.py:RUNTIME` classe explicitement le nouveau fichier comme `IMAGE_TRANSPORT`. **Le cron installé reste portal-only**, pas une preuve de déploiement; ne pas exécuter `--apply`.
- Tests ajoutés aux tests existants `tests/test_demo_v2.py` : route et liens, six étapes offline, fichier présent, classification transport + Dockerfile. Pas de nouveau workflow. CI `quality.yml` à attendre sur le SHA final ; aucun test navigateur ni Debian réalisé par ce passage.
- Contrats: `/demo-studio/business-story` sert le fichier statique, sans token, sans lecture Core ni mutation. `/demo-studio/run/{rid}` et proxy AI Ledger inchangés. RBAC tenant sur Core reste fail-closed; cette histoire n'est pas un run observé.
- **DEMO_READY=NOT_READY (terrain) / READY_FOR_STABLE=BLOCKED** tant que CI sur HEAD, test navigateur, packaging réel, rollback, applied.sha et smoke read-only ne sont pas attestés.
- NOT_TESTED: navigateur interactif, Debian, SAN→Payments runtime, Policy/HITL authentique, Evidence tenant-scoped, rollback.
- Prochain lot exclusivement 5/5 : confirmer CI sur SHA exact, inspection packaging opérateur, test navigateur + URL `/demo-studio/business-story` et rollback; aucune promotion stable sans gates.
