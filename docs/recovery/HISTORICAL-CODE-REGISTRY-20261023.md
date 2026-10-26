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

## Passe d'inspection des archives cumulatives (26 octobre 2026)

Cette passe a porté sur des octets d'archives présents dans la Library, sans installer ni exécuter de code historique et sans déposer les ZIP originaux dans GitHub. Les empreintes ci-dessous sont calculées sur l'archive complète obtenue ; les dates sont celles du dépôt de la copie dans la Library, pas nécessairement les dates de création du code.

| Archive source | SHA-256 de l'archive | Contenu observé | Vérifications effectuées | Décision de réemploi |
|---|---|---|---|---|
| `AIOPS-V21310-STAR-PORTAL.zip` (22 oct.) | `cdca139131dbbac7adb2f811077c25e94dd01899a6ec33c37ea067d26a351d87` | 8 membres ; `portal_demo_public_v21310.py` = 1 762 octets | ZIP/CRC PASS, aucune entrée dupliquée, AST du module PASS ; SHA-256 du module `5bee897914ec958af0f715f24eee229b9f9539a3df5da4f9c43cb8746ad60ee0` | Le module et son asset sont déjà représentés dans le code courant ; ne pas recopier l'archive ni son installateur. |
| `AIOPS-V2.13.4-HYBRID-REPLAY-STAR.zip` (22 oct.) | `83d71029197e0c23310a5e466ad68dfcb6e04683160bc3e0e5b9302edbe85550` | 10 membres ; 5 sources Python dont assembleur et générateur de replay | ZIP/CRC PASS, aucune entrée dupliquée ; AST PASS pour les 5 modules Python | Référence historique de replay. `build_real_replay.py` et l'assembleur ne sont pas exécutés ni promus : les entrées/effets fichiers et les sources Core doivent être contrôlés. |
| `AIOPS-V2.13.6-DEMO-FINALE-CUMULATIVE.zip` (22 oct.) | `d7ab89a5e5b9e7ce15bbb140c3bc1c55cf601a43a1029c019bd61f2c3990bb9e` | 26 membres ; inclut le ZIP V2.13.4, 4 fichiers bytecode `__pycache__`, des rapports opérateur historiques et un ZIP HLD/LLD imbriqué de 9 470 244 octets | ZIP/CRC PASS, aucune entrée dupliquée ; les 5 sources Python du dossier de démonstration passent AST ; plusieurs HTML, guides, tests et outils ont les mêmes SHA-256 que leurs homologues du V2.13.4 | Dédupliquer les copies exactes plutôt que les réimporter. Exclure le bytecode et les rapports historiques de toute preuve. L'archive HLD/LLD imbriquée reste à inspecter séparément avant réemploi. |
| `AIOPS-KIT-DEPLOIEMENT-V2.15.0-PORTAIL-UNIQUE-20261025.zip` (24 oct.) | `0d9503679c71eff54c980ad20f630f9831591bccec7c91f9814940b7750b1dd3` | 15 membres ; kit d'audit et contrat de convergence, avec ZIP V2.14.1 imbriqué | ZIP/CRC PASS, aucune entrée dupliquée ; manifeste présent ; AST PASS pour les 3 scripts Python extérieurs | Contrat utile pour les étapes read-only. Ce n'est pas un clone du dépôt ni une intégration du portail. Les scripts n'ont pas été exécutés sur l'hôte cible. |
| ZIP V2.14.1 imbriqué dans V2.15.0 | `ac74e9329f6ee0dc7fe5eb84704117059a37774179b5b9a5b4f47770f968b669` | 30 membres, référencés par le manifeste V2.15.0 | ZIP/CRC PASS, aucune entrée dupliquée ni chemin dangereux détecté ; 4 scripts Python passent AST | Patrimoine seulement ; audit de l'authentification, des destinations et des effets requis avant portage. |
| `AIOPS-HISTORICAL-RECOVERY-CATALOG-20261023.zip` (23 oct.) | `198904d4e2e4df27a41a00e40de7881d84438a5415f40862f094cf4117194bfa` | 11 entrées ZIP ; inventaire CSV des chemins, compte-rendus et deux fichiers Python V2.12.5 | ZIP/CRC PASS, aucune entrée dupliquée ; AST PASS sur les deux fichiers Python | Complément de l'inventaire, pas une source opérationnelle autonome. |

### Déduplication et limites de sécurité de cette passe

- Le ZIP V2.13.6 contient le même ZIP V2.13.4, dont le hash interne est exactement `83d71029197e0c23310a5e466ad68dfcb6e04683160bc3e0e5b9302edbe85550`. Plusieurs sources et tests ont également le même SHA-256 octet pour octet ; la copie cumulative ne doit pas être promue une seconde fois.
- Le ZIP V2.15.0 inclut le V2.14.1 comme archive imbriquée, avec hash `ac74e9329f6ee0dc7fe5eb84704117059a37774179b5b9a5b4f47770f968b669`. Le manifeste couvre les fichiers listés ; les comptes-rendus historiques ne remplacent pas une exécution de test au HEAD actuel.
- Un scan local de motifs connus de clés/tokens n'a signalé aucune correspondance dans les sources texte inspectées. Ce scan est heuristique, ne prouve pas l'absence absolue de secret et n'autorise pas la publication des ZIP bruts.
- Les scripts `inventory.py` et `check-http.py` du V2.15.0 sont lus et passés à AST ; ils n'ont pas été exécutés. Le test historique `inventory.scan()` lance `ss`, `docker ps` et `podman ps` sur la machine d'exécution qui l'appelle : ne pas exécuter ce test sur un contexte de production. Un futur test devra mocker ces commandes.
- Une analyse syntaxique AST prouve seulement que Python peut analyser le texte. Elle ne qualifie ni dépendances, ni authentification, ni fonctions E2E. Les archives originales restent hors de GitHub ; cette fiche en conserve les références d'empreinte.

## Suivi
Cette première passe n'est **pas exhaustive** sur toutes les fenêtres de conversations du 1er au 23 octobre : il reste à indexer les autres journaux, archives et historiques exportés, en s'appuyant sur le consolidateur Windows V2.0. Faire évoluer ce registre à chaque nouvelle découverte, avec commit et PR avant fusion.
