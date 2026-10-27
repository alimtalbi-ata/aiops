# Automation P0 Vidéo & preuves — 2026-10-27 20:52 Europe/Paris

## Base et périmètre

- Dépôt : `alimtalbi-ata/aiops`. Base `main` observée : `92108b3bd87a15e0b312a689c0324f2c8e572e55` (PR #43). Branche cible préexistante : `feat/evidence-backed-demo-video-20261027`, PR draft #43, HEAD initial du lot : `ce6ed32f393a73040514bbfb7400ba0db0f127c2`.
- Lecture : main (`quality.yml`, portail, continuité, architecture), PR ouvertes #36/#37/#39/#41/#43 ainsi que #44/#45; lecture ciblée PR #36 (`star_snapshot_browser.py`, `star_browser_capture_tasks.py`, `star_browser_request_fence.py`). Pas de merge massif.
- Objectif : préparer la capture de cinq vues **réelles** en session opérateur, sans navigateur réel ni serveur accessible pendant ce lot.

## Fichiers et commits

1. `01e47d68d7df438a10c2de59cdb598be3b9f1edb` : `demo/evidence_browser_capture.py` — Playwright opt-in, requêtes GET allowlist, redactions obligatoires, IDs liés et manifeste non attesté.
2. `e41dab0991225b51ce2cd682051500d293676963` : `tests/test_evidence_browser_capture.py` — 13 tests offline, incluant refus CI, origine, credentials, requêtes non approuvées, masques et autorisation.
3. `1773cb16bede006c0bf10b1ac27b3bfdf0b190a8` : `.github/workflows/quality.yml` — réutilisation des quality gates existantes, sans CI parallèle.
4. `95ddaf917466b5b020395134d550537a4fd94d71` : `docs/demo/PLAYWRIGHT-EVIDENCE-CAPTURE.md` — procédure, sessions privées, limitations.
5. `316ebf50151a81e5b645f5d8c2f8c664273a3be5` : `tests/test_evidence_video.py` — correction des fixtures PNG qui contenaient des échappements littéraux invalides; remplacement par PNG réellement décodables.

## Tests et preuves observées

- GitHub Actions `quality.yml` PR #43, run **40573175943** : **FAIL** (confirmé via jobs/logs). Sept tests policy PASS. `test_evidence_video.py` : 7 OK / 2 ERROR (`test_five_present`, `test_no_runtime_attestation`), car IHDR des fixtures était invalide. Les 13 nouveaux tests de capture ont été **SKIPPED** à cause de cet échec précédent. Lien : https://github.com/alimtalbi-ata/aiops/actions/runs/40573175943
- Correction commit `316ebf5` déposée; résultat CI de cette correction **PENDING/NOT_VERIFIED** au moment du journal. Aucun PASS déclaré sur le nouveau code.
- Aucun Playwright réel, ffmpeg, MP4 ou session authentifiée exécuté pendant ce lot. **NOT_TESTED** pour la capture runtime et le rendu MP4. Aucun accès Debian, aucune action LIVE.
- Les fixtures PNG de test restent des images synthétiques de test, **pas des preuves runtime**.

## Risques, blocages, prochain micro-lot

- Sans URLs approuvées, sessions Playwright privées, masques revus et captures authentifiées : `LIVE_CAPTURE_BLOCKED`; aucun mock ne peut se substituer aux cinq vues.
- Les masques CSS ne garantissent pas la confidentialité de toute la capture; revue opérateur et traçabilité de session restent obligatoires.
- Le filtre GET exact peut bloquer les ressources nécessaires aux applications; adapter les allowlists après inspection autorisée, jamais les désactiver silencieusement.
- Prochain micro-lot : confirmer Actions verts, corriger les erreurs, ajouter un test ffmpeg de décodage/rendu MP4+SRT avec vraies fixtures PNG, puis brancher Evidence Studio au portail avec qualification d'accès.
- PR #43 demeure **draft**, sans merge ni déploiement tant que les checks et l'intégration ne sont pas qualifiés.
