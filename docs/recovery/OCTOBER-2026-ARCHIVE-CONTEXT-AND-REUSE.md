# AIOps — Archaeology of October 2026 assets (verified inventory)

**Status:** historical-source inventory, not a deployment qualification. Sources copied from ChatGPT Library archives in the recovery workspace. Preserve the current Debian :17777 portal and V1 Docker bridge; no automated production import.

## Recovered concrete archives and intended reuse

| Archive | Verified contents | Context / purpose | Reuse decision |
|---|---|---|---|
| AIOPS-V2.13.6-DEMO-FINALE-CUMULATIVE.zip | Executive Theater, Hybrid Command, STAR Demo, Chromium scripts, replay tooling, qualification files | Executive incident story, visual replay and presenter guide | **P0** review HTML/tools; compare with PR #36 before rewriting UI |
| AIOPS-V2.13.4-HYBRID-REPLAY-STAR.zip | Hybrid Command/STAR HTML, build_real_replay.py, assemble_hybrid.py, unit and Chromium tests | Hybrid historical replay and scenario preparation | **P0** reuse replay contracts and cinematic tests |
| AIOPS-V21310-STAR-PORTAL.zip | portal_demo_public_v21310.py, install.py, public Executive Theater HTML, tests | Portal STAR candidate prior to recent isolated renderers | **P0** reconcile installer/route with current port 17777 (do not run installer) |
| AIOPS-V2139.3-PORTAL-UNIQUE.zip | portal-control.sh, README | Port 17777 operational control | **P0** inspect, never execute on live host without validation |
| AIOPS-V2.12.7-Offline-Consolidated.zip | qualification of Evidence Center and ACME browser, historical summarizer, tests | Evidence integrity and browser qualification | **P1** reuse and port test invariants |
| AIOPS-V2.13.0-Automated-Showcase.zip | showcase builder, HTML/manifest, unit tests | Synthetic/demo storytelling | **P1** archive and check factual provenance |
| AIOps2-DEMO-Hub-V1.zip | demo_hub.py, install.sh | Demonstration hub | **P1** inspect with security boundaries |
| AIOps-History-Consolidator-Windows-V2.0.zip | consolidation CLI, decision/requirements/dependency/source audits, Windows command entrypoints | Reconstruct developer history on Windows | **P0** reuse tool for remaining history after safe inputs |
| AIOPS-V2.12.5-Historical-Summary-Source.zip | historical summarizer and tests | Core/AI Ledger/Evidence historical summary | **P1** recover original tests/source if absent |

## Historical logs from October 1–19

Historical logs were collected for October 1, 4, 7, 12, 14, 15, 17, 19. October 15 Playwright logs mention `playwright-evidence-campaign.py`, `playwright-demo-screens.py`, `demo-multistack-capture.py` in F20.13 evidence kit. The pasted terminal heredocs are incomplete/mangled; do NOT present them as an executable full original.

The October 15 multistack run recorded a Grafana **login** page at `127.0.0.1:3000/login`, not an authenticated incident panel, and GLPI/n8n HTTP reachability cannot establish validated captures. Historical logs are evidence of a past command, not a current production qualification.

## Recovery protocol per component

1. Preserve exact source/archive identity (path, SHA256, chronology, version).
2. State user case, interfaces, dependencies, inputs/outputs and safety constraints.
3. Distinguish *archive verified*, *syntax/test verified*, *runtime E2E verified*, *historical mention only*.
4. Document what was lost and the present replacement/overlap.
5. Import on a **dedicated branch / PR** after secret review; do not silently overwrite main, workflows, DB or live app.
6. Run unit tests and isolated Chromium/Temporal stack before integration to :17777.
7. Keep screenshots, personal data, DB dumps, tokens and browser profiles out of Git.

## Kits F20.13 et export du portail : inspection du 26 octobre

Les ZIP historiques ont été matérialisés dans un espace de travail temporaire, inspectés hors ligne puis rapprochés de la lignée V2.13.1–V2.13.6.1. Le registre HISTORICAL-CODE-REGISTRY-20261023.md conserve les SHA originaux et l'analyse par archive. Aucun ZIP original n'a été ajouté à GitHub.

- F20.13 v0.2 Evidence kit : besoin visé = campagne multi-écrans. Réalité constatée = capture de baseline seulement, pour un contrat annoncé de 13 vues. Les scripts citent les ports 8141/8099/8110. Les entrées/sorties ne prouvent pas les 13 écrans ; ne pas réutiliser la procédure d'exécution telle quelle.
- F20.13 v0.4.2 / v0.5 Client Demo : story/cues Playwright pour UCP, Grafana, n8n et GLPI. Dépendances historiques navigateur/HTTP sur 8141/3000/5678/8080. Le manifeste v0.5 n'inclut pas les ID d'incident/ticket, timestamp ni hash de PNG. Il autorise aussi un URL de trigger arbitraire ou une commande shell : ces capacités sont interdites pour le portage.
- Export complet du 15 octobre : décrit des routes, composants, inventaires et sauvegardes historiques. C'est un snapshot daté, non la preuve de l'état du 26 octobre. L'export complet et ses tarballs ne doivent pas rejoindre GitHub ; la revue de confidentialité manuelle reste obligatoire même en l'absence de motifs de tokens connus.
- V2.13.6.1 : 14 tests Python historiques ont été reproduits dans un répertoire temporaire isolé. Le manifeste primaire a cinq divergences (quatre .pyc obsolètes et README), tandis que le manifeste de release indépendant est concordant pour 31 entrées. Sources de référence, mais pas preuves runtime ; ne promouvoir ni bytecode ni rapports opérateur.
- V2.13.4 replay : les sources du générateur de replay et du test apparaissent sous forme de copies identiques dans cinq archives. L'assembleur est déjà présent à l'identique dans recovery/legacy_v2134/tools/assemble_hybrid.py. Toute restauration supplémentaire commence donc par comparaison SHA/chemin, puis test d'interface/provenance, pas par recopie du ZIP cumulatif.

### Contrat d'intégration cible

Convertir le plan F20.13 en cues allowlistés dans le portail unique :17777. Chaque cue doit porter le chemin d'écran approuvé, l'identifiant applicatif, run_id, incident_id, ticket_id s'il existe, horodatage de capture, SHA-256 du PNG et provenance/authentification effectivement observées. Absence d'écran/ticket/run, page de login, timeout, événement hors fenêtre ou champ manquant => cue non qualifié, jamais remplacé par un écran HTML local. Aucun trigger live. Les essais utilisent des données synthétiques. L'E2E runtime cible demeure non qualifié.

### Migration incrémentale — 27 octobre 2026 : liaison des événements STAR

La source actuelle demo/star_event_source_binding.py apporte une validation défensive des octets d'événement pour les checkpoints : identité canonique, horodatage comparé, SHA-256 exact, refus des symlinks et lecture par descripteurs. Sa source, sa suite de tests, son workflow offline et sa fiche technique sont intégrés au kit cumulatif épinglé ; le test du kit vérifie les octets embarqués contre le checkout. Cette migration est un successeur sûr et limité, pas la restauration intégrale de F20.13 ni une authentification des backends. Les sources historiques complètes et l'E2E runtime restent à qualifier.

## Reconstruction priority

P0 portal V2.13.6 + V2.13.10 reconciliation, camera/replay STAR + Chromium scripts, decision pipeline Analyst/Critic/Policy/HITL. P1 Evidence/AI Ledger + CMDB/cascade correlation + Temporal crash recovery. P2 showcase/media, history consolidator and Windows operator UX.

**Limitation:** This is a partial Library sample, not an exhaustive extraction of every chat message since October 1. Later catalog generations must be incrementally deduplicated and versioned.
