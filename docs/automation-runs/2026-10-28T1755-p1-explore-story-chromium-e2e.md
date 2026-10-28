# P1 recette — Chromium réel Explore / Story ACME — 2026-10-28 17:55 CET

## Coordination et point de départ

- HEAD `main` vérifié avant branche et re-vérifié avant correction : `7659cc32b573e0bb847221b9d1dc5081039a0f3e` (PR #132, Explore/Story déjà fusionné).
- Branche dédiée `fix/e2e-explore-story-browser-20261028-1751`, [PR draft #136](https://github.com/alimtalbi-ata/aiops/pull/136) ciblant `main` ; aucun changement aux branches des autres créneaux.
- Sources : `docs/PROJECT-CONTINUITY.md`, `docs/DEMO-REPLAY-STORY.md`, derniers journaux P0 Explore/Story, NOC, Worker, portail ; `app/portal/acme_explore_story.py`, client JS, modèle d'impact, tests et `.github/workflows/quality.yml`. PR #36/#43 (réemploi des frontières), #121 (Evidence), #127 (60 CI), #128 (timeline), #133 (contrat scénario) examinées.
- Réemploi strict du portail FastAPI, des fixtures ACME et de `quality.yml` existants. Aucune CI indépendante créée.

## Micro-livraison verticale et fichiers

- `tests/test_explore_story_playwright_e2e.py` : véritable processus HTTP FastAPI sur loopback + navigateur Chromium Playwright ; tests d'accès anonyme et mauvais jeton (401), navigation Explore/Story, avance/pause, 9 checkpoints MISSING, cohérence du Run synthétique avec la page Impact, effacement du jeton. Filtrage réseau navigateur à l'origine loopback et blocage des services upstream. Aucun faux backend.
- `.github/workflows/quality.yml` : installation Chromium isolée, exécution du test et publication d'un artefact UI de provenance `CI_SIMULATED_PORTAL` dans le job existant `policy-and-static` ; conservation 7 jours. Le reste des jobs Core/PostgreSQL et Grafana reste inchangé.
- `app/portal/acme_explore_story.py` : `overflow-wrap:anywhere` pour le SHA-256 de fixture. Défaut visuel observé sur la **vraie capture Chromium CI initiale** : le hash débordait dans la carte adjacente.
- Le test navigateur ajoute une assertion de non-débordement du SHA avant capture ; ce correctif reste à requalifier sur le HEAD final.
- Ce journal : `docs/automation-runs/2026-10-28T1755-p1-explore-story-chromium-e2e.md`.

## Commits et validation réellement constatée

- `78085609b6a590f85155e5fffbfcdd4fce61ca02` — test Playwright E2E.
- `bc4550e058c5e9810f098b533d1a9a9578ed94d1` — adaptation `quality.yml`.
- `d3d9dcb56cabec58da5a6e6dc80cf75192e34002` — correction CSS.
- `c6c224e72442d81cfd6d6f4cb11136cc8e18aeef` — assertion visuelle anti-débordement.
- [CI initiale push #40730368405](https://github.com/alimtalbi-ata/aiops/actions/runs/40730368405), SHA `bc4550e058c5e9810f098b533d1a9a9578ed94d1` : **SUCCESS confirmé** pour les 3 jobs ; étapes installation Chromium, E2E navigateur, publication artefact, audit et Compose **SUCCESS**. Ce succès précède le correctif CSS.
- Artefact réel [`acme-explore-story-ci-simulated` #12833518771](https://github.com/alimtalbi-ata/aiops/actions/runs/40730368405/artifacts/12833518771) téléchargé et inspecté. PNG `explore-story-ci-simulated.png` ; SHA-256 vérifié indépendamment : `3f57aadc3ece6144a159c964fa2864cc4c9378f1cc3d3f7ef229b0db9e94d2ca`, identique au reçu JSON. Horodatage réel de capture `2026-10-28T16:53:56.119885+00:00`, Run `SIM-ACME-254B1E4DF518E38F`, fixture SHA `254b1e4df518e38febc3bd25347462b67b24a39228b744a0235ef33f1578faed`.
- Capture : **preuve authentique d'un navigateur Chromium sur portail CI éphémère synthétique**, pas preuve d'une session applicative LIVE. `runtime_authenticated=false`, `production_qualified=false`, `privacy_reviewed=false` et aucun ticket GLPI réel.
- **CI du HEAD final (CSS + assertion + journal) : en attente de vérification après publication**, ne pas marquer PASS par anticipation.

## Contrat et sécurité

- Contrats HTTP existants **inchangés** : `POST /api/demo/explore-story/control`, `GET /demo/explore-story`, `GET /demo/acme-impact`.
- Nouveau contrat de **fichier d'observation CI uniquement** : `aiops.ci-browser-observation.v1`, avec `provenance=CI_SIMULATED_PORTAL`, SHA du PNG, SHA du fixture, IDs synthétiques, horodatage UTC, SHA Git, aucune attestation runtime. Ne pas importer comme reçu LIVE dans Evidence Studio.
- Aucun appel à Debian, aucune écriture GLPI, aucune remédiation LIVE, aucun NGX, aucun déploiement. Le test de navigation n'est pas une intégration Core/Temporal/GLPI/n8n/Thruk ; seuls le serveur portail et le navigateur sont réels.

## Blocages priorisés / transmission aux autres lots

1. **P0 — E2E métier inter-services : NOT_TESTED**. Explore/Story restent une projection locale ; raccorder les contrats #133 (events), #128 (Evidence) et les services Core/GLPI sous ACL tenant réelle avant une démo complète.
2. **P0 — Provenance et confidentialité : BLOCKED**. Capture CI synthétique vérifiable mais non revue opérateur, sans session réelle Thruk/Grafana/n8n/GLPI ; aucune vidéo client autorisée.
3. **P1 — Concurrence des PR :** #127 ajoute 60 CI, #128 timeline, #133 événements ; garder leurs espaces d'IDs et SHA cohérents, ne pas remplacer les IDs synthétiques par des IDs runtime.
4. **P1 — Présentation :** le débordement du SHA constaté sur PNG initial est corrigé en source ; attendre l'assertion navigateur du HEAD final et inspecter son nouvel artefact.

Prochain micro-lot : vérifier les checks du dernier commit, inspecter le nouveau PNG ; ensuite ajouter un E2E navigateur reliant le contrat canonique #133 et la timeline #128 **après intégration contrôlée** de ces PR. Pas de storyboard vidéo avant E2E opérationnel.
