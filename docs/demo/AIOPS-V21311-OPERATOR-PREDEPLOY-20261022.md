# V2.13.11 — Préqualification opérateur, 2026-10-22

Sur SRV-DEB-05, l'opérateur a récupéré la source du théâtre STAR et le test depuis la branche feat/v21310-star-portal-continuity-20261022 par FETCH_HEAD, vers une copie isolée du source de V2.13.10.

- AIOPS_V21311_SOURCE=PASS
- Playwright/Chromium sur fichier local: 12 contrôles booléens sur 12 PASS, erreurs JavaScript [].
- Contrôles: loaded, twelve_steps, initial, next, previous, direct_step, reset, pause_label, resume_label, keyboard, provenance, no_console_errors.
- Docker build aiops2-portal:v21311: PASS (Docker rootless).
- Import FastAPI hors réseau avec routes /demo/, /demo/star, /demo-studio et présence de l'asset: AIOPS_V21311_IMAGE=PASS.
- **Aucune qualification HTTP ni browser de V2.13.11 déployée sur 17777 à ce stade**; la version active précédemment qualifiée est V2.13.10.
- Aucun test DGX, Core, Policy LIVE ni relecture historique n'est revendiqué.

Suivant: bascule de l'unique service aiops2-portal avec sauvegarde de l'image précédente, tests HTTP (200/403) et contrôle image; rollback en cas d'échec; navigateur sur la route réelle après bascule; conserver les fichiers Compose locaux et ne pas activer la remédiation LIVE.
