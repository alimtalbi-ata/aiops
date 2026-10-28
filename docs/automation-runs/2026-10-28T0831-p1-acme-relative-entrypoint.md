# P1 ACME — point d'entrée relatif du portail unique

- **Horaire :** 2026-10-28 08:31 Europe/Paris (début de l'exécution ; vérification CI après création PR).
- **Repository :** `alimtalbi-ata/aiops`.
- **SHA main de départ :** `3a50c1c1f6c36a62272bd6b669086866a4708ee3` (revalidé avant création de branche, puis avant journal).
- **Branche dédiée :** `fix/p1-acme-relative-entrypoint-20261028-0831`.
- **PR :** https://github.com/alimtalbi-ata/aiops/pull/107 (draft, base `main`).
- **Code commit :** `c6df7fc5fbc1248440b4ea39067fc86090b38f9e`.
- **Fichiers code/test/docs :** `app/portal/acme_impact_read_model.py`, `tests/test_acme_impact_read_model.py`, `docs/demo/ACME-SAN-PAYMENTS-IMPACT-20261027.md`, `docs/PROJECT-CONTINUITY.md`, ce journal.

## Incrément

- Réutilisation de la vue synthétique ACME provenant du portage ciblé de PR #36, déjà sur `main`. Suppression de l'URL Debian codée en dur dans le champ `entrypoint` ; retour du chemin relatif `/demo/acme-impact` et de sa provenance explicite `RELATIVE_PORTAL_ROUTE_NOT_DEPLOYMENT_URL`.
- Ajout d'un lien local de retour vers `/` dans la page de démonstration ; aucune connexion à un hôte externe.
- Test négatif et de non-régression : requêtes ASGI avec Host arbitraire, absence d'IP Debian dans le JSON et le HTML, absence d'attestation runtime.

## Tests réellement exécutés

- **GitHub Actions / PR `quality.yml` :** https://github.com/alimtalbi-ata/aiops/actions/runs/40650794454 — `completed/success` sur `c6df7fc5fbc1248440b4ea39067fc86090b38f9e`. Étapes confirmées : compilation Python, tests Policy, portail, NOC, ACME (dont nouveau test), préflight secrets, audit statique, `docker compose config`.
- **GitHub Actions / push `quality.yml` :** https://github.com/alimtalbi-ata/aiops/actions/runs/40650778675 — `completed/success` sur le même SHA.
- **Tests locaux :** `NOT_TESTED` (accès réseau au dépôt impossible depuis le conteneur de travail ; les tests ont été exécutés sur GitHub Actions).
- **Intégration réelle Core/PostgreSQL/Temporal/GLPI :** `NOT_TESTED`. Aucun service conteneurisé applicatif qualifié par ce lot ; `docker compose config` ne démarre pas la stack.
- **Ollama 4B / NGX 192B :** `NOT_TESTED`, aucun appel LLM. Aucune simulation matérielle supplémentaire.
- **Captures authentifiées, vidéo finale, Debian et LIVE :** `NOT_TESTED` / aucun accès.

## Risques et blocages

- La PR #77 modifie également la topologie/vue ACME ; réconcilier ce changement de trois lignes au moment de l'intégration, sans fusion massive.
- La route de lecture ACME reste une source synthétique publique, pas un read-model CMDB ou GLPI autorisé par tenant. `ticket_id=null`, checkpoints `MISSING`, remédiation LIVE interdite.
- La PR #80 traite séparément l'authentification de la route d'écriture `POST /api/demo` : cette PR ne la modifie pas.

## Prochain micro-lot

- Réconcilier les PR #77/#80 avec `main` et leurs tests sans écraser les branches existantes ; qualifier ensuite le rattachement des identifiants Incident/Run/GLPI avec services éphémères et ACL serveur.
