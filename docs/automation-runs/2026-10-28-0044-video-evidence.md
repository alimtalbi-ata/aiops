# P0 Vidéo & preuves — 2026-10-28 00:44 CET

## État inspecté avant modification
- Dépôt : `alimtalbi-ata/aiops`. `main` HEAD vérifié via comparaison GitHub : `0603e86a26978873c3b6196098674932d3378499`.
- PR #43 HEAD initial : `a6ba2106bb72997b0fa54bd18a086c45a2a7edc8`; branche `feat/evidence-backed-demo-video-20261027`, PR draft, divergence `main` (40 commits ahead, 7 behind après les changements).
- PR #36 (code STAR, capture, manifest, video), #37 (visibilité E2E), #39 (roadmap/continuité), #41 (Debian) et #43 inspectées via GitHub; roadmap lue depuis PR #39 et continuité depuis main/PR #43. Pas de merge massif.
- Risque identifié : `page.route("**/*", ...)` intercepte les requêtes de la page cible mais pas les premières requêtes des popups; WebSocket n'est pas soumis à ce routeur HTTP. Un script tiers pourrait émettre une requête hors du garde-fou de capture.

## Modifications livrées
- `cd9d7574b59171b7b51eba4a63f2c915562b00b4` : `demo/evidence_browser_capture.py`. Installation du garde-fou au niveau du **contexte** Playwright pour couvrir popups/iframes, et fermeture systématique des WebSockets. Absence de `route_web_socket` = BLOCKED, sans dégradation silencieuse.
- `1d9ebe2e2fbe502ffd4129703fbed1e03ef11ddd` : `tests/test_evidence_browser_capture.py`. Tests négatifs offline des navigations popup, POST, origine non approuvée, ressource inconnue, WebSocket, et test de non-régression GET explicitement autorisé.
- `1bb15b51750a6c9ce995228495b36624e61e0d53` : `docs/demo/PLAYWRIGHT-EVIDENCE-CAPTURE.md`. Limites et politique de refus documentées.
- PR existante : https://github.com/alimtalbi-ata/aiops/pull/43 (draft, non fusionnée). Aucun accès Debian, déploiement ni action LIVE.

## Qualification réelle
- `NOT_EXECUTED` : tests locaux sur checkout réel indisponibles dans cette exécution. Les nouveaux tests sont écrits mais leur résultat n'est **pas** revendiqué.
- `NOT_CONFIRMED` : interrogation GitHub Actions sur le HEAD `1bb15b5` immédiatement après commit : aucun run PR retourné. Le workflow existant `.github/workflows/quality.yml` inclut déjà `test_evidence_browser_capture.py`; aucun nouveau workflow CI créé.
- `NOT_TESTED` : navigateur Chromium réel, FFmpeg du HEAD final, services en conteneurs éphémères, cinq captures authentifiées et vidéo LIVE. Aucune fixture n'est présentée comme preuve.
- Provenance inchangée : `OPERATOR_SUPPLIED_UNATTESTED`, `runtime_authenticated=false`, `production_qualified=false`.

## Risques et prochain micro-lot
- La capture est volontairement BLOCKED si Playwright ne dispose pas du routeur WebSocket; les applications qui nécessitent WebSocket doivent être revues, pas exemptées.
- Le routage ne remplace pas une revue humaine des pixels, des sessions et de l'absence de données privées; les captures restent non attestées.
- Vérifier les checks de la PR sur le HEAD après ce journal; corriger toute régression. Ensuite résoudre les conflits PR #43 de façon ciblée sans écraser main, puis qualifier un rendu MP4/SRT à partir de captures opérateur réelles autorisées.
