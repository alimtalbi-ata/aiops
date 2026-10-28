# P0 Vidéo & preuves — 2026-10-28 02:47 CET

## Source et état initial
- Dépôt `alimtalbi-ata/aiops`; `main` vérifié via compare GitHub : `0603e86a26978873c3b6196098674932d3378499`.
- PR #43 : https://github.com/alimtalbi-ata/aiops/pull/43 ; HEAD de départ `53dfc3f3d593e1dda62d793b739b021316bde3a6`, draft, non fusionnable.
- PR #36 (notamment `demo/star_browser_request_fence.py`), #37, #39 (roadmap/continuité), #41 et #43 inspectées; lecture `README.md`, `docs/PROJECT-CONTINUITY.md`, `docs/DEVELOPMENT-ROADMAP-2026-10-27.md` et `.github/workflows/quality.yml`. Aucun merge massif.
- Risque identifié : une URL GET exacte autorisée dans `approved_get_urls` pouvait aussi être chargée en tant que `document` secondaire, `eventsource` ou type inconnu, alors que PR #36 limite les types de sous-ressources.

## Modifications et commits
- `2ec09f27875a0219775f3b2f5831fbb72d86615d` — `demo/evidence_browser_capture.py` : portage ciblé du filtre `RESOURCE_TYPES` de PR #36, type de ressource lu sur la requête Playwright, refus des types actifs/inconnus; le plan refuse explicitement les GET avec query (déjà rejetés par `origin`, test de non-régression).
- `1d672d3c7799d74626ed2d9b2de35e907e850f3f` — `tests/test_evidence_browser_capture.py` : tests positifs/négatifs de types, refus de POST, document, EventSource et URL avec query; attentes du faux contexte Playwright actualisées.
- `e34e93eb18f02ae824a5eff95ec6a58233e1706d` — `docs/demo/PLAYWRIGHT-EVIDENCE-CAPTURE.md` : contrat, limites et blocages.
- `a64b1145dc11a957e31bb405c42cef047b213202` — `docs/PROJECT-CONTINUITY.md` : point de continuité.
- Ce journal : `docs/automation-runs/2026-10-28-0247-video-evidence.md`.
- Branche/PR conservées : `feat/evidence-backed-demo-video-20261027`, PR #43 draft. Aucun merge ni déploiement.

## Vérifications réellement exécutées
- Local : `python /tmp/aiops_fence_isolated_20261028.py` : **5 tests réussis** sur une **reproduction isolée** des fonctions pures `origin` et `permits` (navigation, types autorisés/refusés, POST/cross-origin, query). Ce n'est **pas** l'exécution des tests du dépôt ni une validation du navigateur.
- `NOT_EXECUTED` : `python -m unittest discover -s tests -p "test_evidence_browser_capture.py" -v` sur le vrai checkout : GitHub non résolu en DNS dans l'environnement local; les fichiers du dépôt ont été lus et modifiés via connecteur GitHub.
- `NOT_CONFIRMED` : `.github/workflows/quality.yml` sur HEAD `a64b1145`; GitHub Actions retourne **zéro exécution PR** à la vérification. Aucun statut PASS CI revendiqué. Le workflow existant contient déjà la suite ciblée; pas de CI parallèle.
- `NOT_TESTED/BLOCKED` : Chromium et applications réelles, conteneurs éphémères d'intégration, assemblage MP4/SRT depuis de vraies captures, NVIDIA NGX/Ollama et Debian. Aucune preuve LIVE ni faux service substitué.

## Risques, rollback et prochain micro-lot
- Les applications avec navigation secondaire, EventSource ou ressources à query peuvent être bloquées : documenter les URL nécessaires et faire valider toute extension de contrat, jamais de fallback silencieux.
- Le filtrage Playwright ne prouve pas l'absence de tous les canaux réseau ni l'identité de la session; `OPERATOR_SUPPLIED_UNATTESTED`, `runtime_authenticated=false`, `production_qualified=false` restent inchangés. GET n'est pas garanti sans effet.
- Revert ciblé des quatre commits de code/tests/docs si nécessaire; pas de `git reset --hard`.
- Prochain micro-lot : exécuter la suite sur un checkout réel ou GitHub Actions, inspecter les erreurs, puis porter les composants utiles de PR #43 vers une branche récente de `main` afin de résoudre les conflits sans écraser les autres PR. Captures authentifiées requises avant toute preuve réelle.
