# P0 — Component registry viewer gate — 2026-10-28 07:01 Europe/Paris

- Départ `main`: `88cb4ed01706ac09bb8e01fdceead422cab2590d` (vérifié avant création de branche).
- Branche dédiée : `fix/p0-portal-components-read-rbac-20261028-0701`.
- PR : à renseigner après création.
- Revue initiale : main, PR ouvertes #36/#37/#39/#41/#43 ; PR connexes #51/#57/#70/#74/#82/#87/#92 ; `README.md`, `docs/PROJECT-CONTINUITY.md`, `docs/ARCHITECTURE-AND-BOUNDARIES.md`, `docs/DECISION-LOG.md`, `docs/COMPONENT-CATALOG-AND-REUSE.md`, `docs/QUALIFICATION-AND-CHANGE-PROTOCOL.md`, `quality.yml`, NOC/portal sources.
- Changement : authentification Bearer viewer sur `GET /api/portal/components` avant lecture du registre, via `_require_portal_read_auth` et `_noc_json_response` réutilisés de NOC/PR36 déjà sur main. Réponses 401/503 non cachables ; navigation toujours `UNKNOWN` et liens `CONFIGURED_UNVERIFIED`.
- Fichiers : `app/portal/main.py`, `tests/test_portal_components_auth.py`, `.github/workflows/quality.yml`, `docs/PROJECT-CONTINUITY.md`, ce journal.
- Commit : à renseigner après création.
- Tests : `quality.yml` GitHub Actions prévu sur PR ; **PENDING/NOT_TESTED** au moment du commit initial, aucun PASS présumé. Les tests HTTP utilisent TestClient, pas des conteneurs réels.
- Risques : `/api/portal/components` nécessite désormais le jeton viewer ; clients anonymes reçoivent 401. La page HTML `/` reste anonyme et peut exposer des liens configurés : RBAC global non résolu. Convergence nécessaire avec PR #74 et #92 (touchent `app/portal/main.py`).
- Blocages : services réels, intégration conteneurs, captures et NGX `NOT_TESTED`. Aucun accès Debian, portail 17777 distant, merge, deploy, ni commande LIVE.
- Prochain micro-lot : convergence ciblée des PR #51/#57/#70/#74 et test E2E sur conteneurs éphémères, sans mocks d'intégration.

## Clôture des contrôles (28 octobre 2026, après CI)

- PR draft : https://github.com/alimtalbi-ata/aiops/pull/98 ; non fusionnée.
- Commit initial code/tests/workflow/docs/journal : `05ae08ec7781be950b80b72730ee99335789fe0b`.
- Commit correctif de test : `8fc4563cabbefc222f5d7e3ea454030f22ab4608`.
- CI initiale : https://github.com/alimtalbi-ata/aiops/actions/runs/40641534587 — **FAILURE**, import de `shared.http` sans jeton interne synthétique ; les étapes suivantes ont été sautées. Correctif : variable CI synthétique avant import dans le test, aucune connexion réseau.
- CI après correctif, même SHA `8fc4563` : https://github.com/alimtalbi-ata/aiops/actions/runs/40641614159 (push) et https://github.com/alimtalbi-ata/aiops/actions/runs/40641620624 (pull_request) — **completed/success**. Vérification des jobs : `policy-and-static` et toutes les étapes success, notamment les 5 tests HTTP d'authentification, compilation Python, tests de politique, navigation, Core/Twin, NOC, RAG synthétique, audit statique et validation `docker compose config`.
- Nature de preuve : **tests unitaires/HTTP in-process et vérification Compose**, pas intégration de services en conteneurs. Aucun modèle Ollama/NGX sollicité, aucun secret de production.
- Le commit de ce complément documentaire déclenche à son tour `quality.yml` : statut final à vérifier sur GitHub ; ne pas transposer automatiquement les résultats des SHA précédents.
