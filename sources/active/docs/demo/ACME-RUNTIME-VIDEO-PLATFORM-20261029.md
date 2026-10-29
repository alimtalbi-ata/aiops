# ACME AIOps2 — inventaire runtime et qualification vidéo (29 octobre 2026)

## Périmètre et provenance

Constats transmis par l'opérateur depuis **SRV-DEB-05** (Debian 13), worktree `~/aiops2-p0-consolidation`, branche `prep/acme-demo-offline-20261029`. Ce document est un relevé de diagnostic, **pas une attestation indépendante de production**. Ne pas confondre HTTP 200, chargement DOM, authentification, preuve métier et qualification LIVE.

## Composants et points d'accès vérifiés

Les conteneurs `aiops2-rebuild-*` incluent Portal, Copilot, n8n, GLPI, Prometheus, Alertmanager, Grafana, Temporal UI, Worker, Core, Policy, Twin, Intelligence, Evidence, Temporal, PostgreSQL, Simulator, ainsi que les dépendances. Les services internes ne sont pas nécessairement publiés sur l'hôte.

| Composant | URL HTTP observée | Résultat |
| --- | --- | --- |
| Portal ACME | `http://10.79.94.202:17777/` | HTTP 200 |
| Demo Studio | `http://10.79.94.202:17777/demo-studio` | HTTP 200, titre ACME Demo Studio |
| Runs | `http://10.79.94.202:17777/runs` | HTTP 200, titre Incidents & Runs |
| Timeline | `http://10.79.94.202:17777/timeline` | HTTP 200 |
| Twin | `http://10.79.94.202:17777/twin` | HTTP 200, titre Digital Twin ACME |
| Evidence | `http://10.79.94.202:17777/evidence` | HTTP 200, titre Preuves & Observabilité |
| Policy | `http://10.79.94.202:17777/policy` | HTTP 200 |
| Copilot | `http://10.79.94.202:17777/copilot` | HTTP 200 |
| Grafana | `http://10.79.94.202:3000/` | HTTP 302 par curl, Chromium aboutit à `/login`, HTTP 200 |
| n8n | `http://10.79.94.202:5678/` | HTTP 200, titre n8n.io - Workflow Automation |
| GLPI | `http://10.79.94.202:8080/` | HTTP 200, titre Authentication - GLPI |
| Prometheus | `http://10.79.94.202:9090/` | HTTP 302 |
| Alertmanager | `http://10.79.94.202:9093/` | HTTP 200 |

L'adresse est celle du réseau privé constaté, non une URL publique. Les ports sont publiés sur `10.79.94.202`, **pas** sur `127.0.0.1` ; les premiers essais loopback ont donc échoué sans indiquer une panne des conteneurs. **Thruk n'a pas été localisé** dans l'inventaire Docker fourni. Ne pas inventer son URL.

## Run examiné : blocage métier, non réussite

Page : `/demo-studio/run/RUN-073A9D4D7B4B767C` — HTTP 200, titre et identifiant visibles. Les mots `Evidence`, `Preuve`, `Policy`, `Critic`, `SAN` sont présents; `Payments` n'a pas été détecté. Cette simple présence textuelle ne prouve aucune exécution réussie.

Relevé de l'interface fourni par l'opérateur :
- `scenario_id: acme-san` ;
- `status: BLOCKED` et `state: BLOCKED` ;
- `DGX_ANALYST / INTELLIGENCE_UNAVAILABLE / BLOCKED / HUMAN_APPROVAL` à `2026-10-29T11:47:19.197529+00:00` ;
- `RUN / STATE_TRANSITION / BLOCKED / BLOCK` à `2026-10-29T11:47:19.238596+00:00` ;
- plusieurs `evidence_ids: []`, mais aussi des entrées avec tableaux non vides (leur contenu n'a pas été inspecté) ;
- plusieurs `synthetic: true` ; `synthetic_evidence_created: false` ;
- interface affichant `Chargement des éléments de preuve…` lors du relevé.

Une recherche de motifs `RUN-*` dans le texte DOM a trouvé **11 identifiants** sur `/demo-studio` et `/runs`, **aucun** sur `/twin` ou `/evidence`. Ce constat ne démontre ni l'absence de données ni la corrélation de bout en bout. L'indisponibilité de l'intelligence est une observation sur **ce run**, pas une preuve que le conteneur Intelligence est arrêté.

**Qualification du run : BLOCKED.** Ne pas présenter comme une remédiation réussie, une preuve LIVE, une chaîne SAN → Payments vérifiée ou une attestation de production. Ne pas autoriser de remédiation LIVE sur cette seule base.

## Composants vidéo dans le dépôt

- `demo/evidence_browser_capture.py` : plan privé, captures Playwright avec garde-fous GET et WebSocket, sélecteurs de preuve et masques; **cinq services obligatoires** : portal, thruk, grafana, n8n, glpi. Capture réelle uniquement après accord opérateur explicite et sessions autorisées.
- `demo/evidence_publish.py` : publication fail-closed des preuves.
- `demo/evidence_video.py` : vérification des images/manifeste et encodage MP4.
- `demo/evidence_video_bundle.py` : bundle H.264 1920×1080, MP4, SRT et reçu de provenance/empreintes.
- `tests/test_evidence_browser_capture.py`, `tests/test_evidence_publish.py`, `tests/test_evidence_video.py`, `tests/test_evidence_video_bundle.py` : **48 tests précédemment rapportés PASS** (27 vidéo + 21 capture); ces tests offline ne valident pas une capture LIVE.

Dépendances runtime observées : FFmpeg/FFprobe 7.1.5, environnement isolé `.venv-video`, Playwright 1.64.1 et lancement Chromium headless réussi. Répertoires privés créés : `~/aiops-video-private/{captures,sessions,bundle}`. Les huit fichiers modules/tests sont présents sur Debian mais apparaissaient `??` (non suivis dans le worktree local) au dernier `git status`; **ne pas lancer `git clean` ou `reset --hard`** avant réconciliation.

Le pipeline vidéo **n'est pas** une plateforme interactive de montage embarquée dans Portal. Aucune vidéo issue des cinq vraies interfaces ni intégration de lecteur vidéo dans Portal n'a été démontrée. Les PNG, sessions, identifiants de connexion et reçus potentiellement sensibles restent hors Git.

## Blocages avant la vidéo probante

1. Localiser/qualifier Thruk ou faire approuver un **nouveau contrat** de capture (ne pas remplacer Thruk silencieusement).
2. Authentifier légalement les sessions des cinq applications; Grafana et GLPI affichent actuellement des écrans de connexion dans le navigateur de diagnostic.
3. Choisir un run/incident/ticket et prouver que l'identifiant apparaît visiblement dans **chacune** des cinq vues; le run actuellement inspecté est BLOCKED.
4. Revoir les URLs, GET de sous-ressources, sélecteurs de preuve, masques, origine et permissions; exécuter d'abord le dry-run.
5. Capturer uniquement après accord explicite, contrôler manuellement chaque PNG, puis produire MP4/SRT/receipt sans attester abusivement la source.

## Références de contrat

- [Capture Playwright](PLAYWRIGHT-EVIDENCE-CAPTURE.md)
- [Pipeline snapshot vidéo](REAL-SNAPSHOT-VIDEO-PIPELINE.md)
- [Bundle MP4/SRT](EVIDENCE-MP4-SRT-BUNDLE-CONTRACT.md)

**Statut global :** interfaces HTTP/Chromium vérifiées; moteur vidéo techniquement testé; chaîne de preuve inter-applications et capture réelle **NOT_TESTED / BLOCKED**.
