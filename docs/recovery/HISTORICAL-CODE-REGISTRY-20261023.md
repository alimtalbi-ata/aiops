# AIOps — registre de récupération historique (1er–23 octobre 2026)

**Statut : archéologie documentaire, PAS une restauration qualifiée en production.**
**Source** : fichiers et journaux ChatGPT (conversations des 1, 4, 7, 12, 14, 15, 17 et 19 octobre), archives ZIP fournies dans les échanges. Les chemins de serveur sont des références historiques, pas la preuve que les fichiers existent encore aujourd'hui.
**Responsable auteur des livrables historiques :** Abdelhalim Talbi.

## Inventaire matériel déjà établi
- 9 ZIP historiques distincts matérialisés, 109 membres non-répertoires inventoriés.
- 10 journaux historiques analysés automatiquement ; 1 664 mentions de chemins recensées (nombre de références, pas nombre de modules réellement présents).
- Les extractions heredoc des logs de terminal sont susceptibles d'avoir été tronquées lors du collage. Un bloc manifestement corrompu ne constitue **pas** du code restauré.
- Les archives binaires ne sont **pas** versées à GitHub : conservation privée, revue des secrets, licences et données avant toute promotion.

## Catalogue fonctionnel (source → objectif → réemploi)
| Source historique | Contexte / objectif initial | Valeur à conserver | Prérequis / limites |
|---|---|---|---|
| AIOps-History-Consolidator-Windows-V2.0.zip | Consolidation des conversations, sources locales et Git ; analyse des décisions, dépendances, qualité et lacunes | 50 fichiers dont commandes Windows, Python et tests | Exécuter sur copies, vérifier parcours de fichiers et confidentialité des échanges |
| AIOPS-V2.12.5-Historical-Summary-Source.zip | Résumé borné Core/AI Ledger/Evidence d'un run historique | Vérification de références, statut Analyst/Critic/Policy, absence d'affirmation LIVE | Identifiant RUN historique codé en dur, à paramétrer ; tests sur fixtures isolées |
| AIOPS-V2.12.7-Offline-Consolidated.zip | Qualification Evidence Center et navigateur ACME à partir d'exports opérateur | Génération de manifests SHA256, refus d'absence d'evidence et des états non-DEMO | Dépend de fichiers de génération non inclus ; pas une attestation externe |
| AIOPS-V2.13.0-Automated-Showcase.zip | Générateur de spectacle exécutif HTML et contrôles | Base d'une cinématique rejouable | Revue CSP/XSS, identité, sources, scénario ; maquette ≠ événement réel |
| AIOPS-V2.13.4-HYBRID-REPLAY-STAR.zip | Replay borné des événements Core, Analyst, Critic, Policy + chronologie HTML | Rejouer sans inventer la causalité, lier aux preuves | Dépend d'exports Core et de la vérification d'identité |
| AIOPS-V2.13.6-DEMO-FINALE-CUMULATIVE.zip | Démo Executive Theater / STAR, guides, replay, Chromium QA, architecture | Reprendre UI, scénarios et vérification navigateur | Certains tests/historiques ne prouvent pas le déploiement actuel |
| AIOPS-V2139.3-PORTAL-UNIQUE.zip | Scripts de contrôle du portail unique 17777 | Vérifier ownership et éviter second portail | Toute action de démarrage/arrêt est interdite en production sans autorisation |
| AIOPS-V21310-STAR-PORTAL.zip | Candidat STAR public, patch FastAPI + assets HTML | Base proche du portail actuel, à comparer avec déploiement | PR #36 demeure non promouvable sans réconciliation du main.py |
| AIOps2-DEMO-Hub-V1.zip | Hub des vues de démonstration | Étudier navigation et accès, sans multiplier les portails | Installer/port non validés pour V1 actuel |

## Fonctionnalités historiques vues dans les chats (code complet non encore établi)
- UCP F20.13 `scripts/playwright-evidence-campaign.py`, `playwright-demo-screens.py`, `demo-multistack-capture.py`, `playwright-evidence-campaign-full.py`, `capture-evidence-v02.py`, `demo-video-capture.py`.
- Captures UCP : 11/13 vues historiques PASS dans une campagne ; AI Decision et Knowledge/RAG échouent sur timeout de capture.
- Grafana : la preuve multistack historique montre `/login` et non le dashboard incident ; **ne pas réutiliser comme preuve d'un incident**.
- GLPI / n8n : disponibilité HTTP ≠ capture d'un ticket ou d'une exécution particulière ; leurs captures doivent être vérifiées avec ID réel et fenêtre temporelle.
- V145/V146 : Decision Cockpit, Evidence Fusion, AI Ledger, Corrélation, HITL, replay, fail-closed Policy, n8n workflows et scénario SAN.
- Temporal / Core V28, reconstruction AIOps2, observabilité Loki/Prometheus/Grafana, UI portal unique et sauvegardes : les références doivent être rapprochées du runtime réel en lecture seule.

## Priorités de reconstruction
1. **P0 récupération** : rechercher tous les kits complets originaux (notamment `AIOps-UCP-F20.13-EVIDENCE-DEMO-KIT-v0.2-RELEASE.zip`) dans les archives privées et dépôt, vérifier SHA256 et dépendances, exclure les secrets.
2. **P0 sécurité** : garder V1 rootful intact, aucune commande LIVE ni redémarrage du bridge V1, conserver l'isolation des `run_id`.
3. **P1 réutiliser** les vrais modules Playwright Chromium et faire correspondre `cue → URL/ID attendu → capture → SHA256 → preuve runtime ou manquante`.
4. **P1 portail** : intégrer à l'unique portail 17777 (pas de second serveur).
5. **P2 historique et contenu** : restauration n8n, scénario SAN P1/Payments P2, Core, Temporal, CMDB, Evidence, Critic et décisions ; tests isolés et PR indépendantes.

## Protocole source récupérée
Chaque fichier remis en circulation reçoit une fiche : **archive/échange/date → origine → rôle → entrées/sorties → dépendances → sécurité → couverture test → état (brut / syntaxe / unitaire / E2E) → incompatibilités → adaptation nécessaire**.

Les artefacts chat, logs intégraux, exports GLPI/Core et captures contenant des données client restent privés. **Aucune source n'est déclarée restaurée opérationnellement parce qu'elle compile.**

## Suivi
Cette première passe n'est **pas exhaustive** sur toutes les fenêtres de conversations du 1er au 23 octobre : il reste à indexer les autres journaux, archives et historiques exportés, en s'appuyant sur le consolidateur Windows V2.0. Faire évoluer ce registre à chaque nouvelle découverte, avec commit et PR avant fusion.
