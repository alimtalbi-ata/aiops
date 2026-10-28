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
