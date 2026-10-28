# P0 — 2026-10-28 07:56 Europe/Paris

- **Dépôt / SHA de départ :** `alimtalbi-ata/aiops` ; `main` `88cb4ed01706ac09bb8e01fdceead422cab2590d` (HEAD vérifié avant branche et modifications).
- **Branche dédiée :** `fix/p0-portal-nav-authenticated-ui-20261028-0756`. Pas de mutation de `main`.
- **Lectures :** PR #36/#37/#39/#41/#43, continuité, architecture, décisions, catalogue, `app/portal/main.py`, registre et workflow qualité. PR #51/#57/#70/#74/#98 inspectées pour chevauchements. Portage ciblé du garde viewer NOC de PR #36 déjà dans `main`, sans merge massif.
- **Changement :** `GET /api/portal/components` refuse les visiteurs anonymes ; le HTML public ne divulgue plus les URL d'intégration ; chargement manuel côté navigateur avec jeton à usage unique, validation de l'enveloppe et rendu DOM sans HTML injecté.
- **Fichiers :** `app/portal/main.py`, `app/portal/portal_navigation_client.js`, `tests/test_portal_navigation_auth.py`, `.github/workflows/quality.yml`, `docs/portal/AUTHENTICATED-NAVIGATION-P0.md`, ce journal.
- **Commits :** `065e2af8` (API + shell), `2232d955` (client), `e3b6d1c2` (tests), `f4543a08` (CI), `3c9a06bf` (docs). HEAD avant journal : `3c9a06bf46404f5dd55f9bfeba75f1129d71445a`.
- **Tests ajoutés :** six cas TestClient (auth absente/invalide, config absente, projection non attestée, absence de fuite HTML, URL rejetée, JS sans stockage). `quality.yml` existant enrichi ; **NOT_TESTED** tant que GitHub Actions n'a pas confirmé le résultat. Tests locaux non exécutés : dépôt non clonable dans l'environnement (résolution DNS GitHub impossible).
- **Risques / blocages :** le HTML historique lit encore Core/Twin sans RBAC ; les commandes DEMO/Copilot restent publiques. Les PR #74/#57/#70/#51 doivent être convergées. Le lien externe n'atteste jamais le service. Pas de services réels en conteneurs CI pour ce lot : `NOT_TESTED`, pas de substitution silencieuse.
- **Prochain micro-lot :** convergence RBAC Core/Twin et commandes, tests de non-régression communs, puis vraie intégration conteneur des services hors LLM.
- **LIVE / Debian :** aucun accès, aucune capture, aucune commande, aucun déploiement, aucun appel NGX.
- **PR et run CI :** renseigner après confirmation GitHub ; ne pas marquer PASS sur cette entrée avant résultat.
