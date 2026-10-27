# AIOps 2.0 — Catalogue des codes candidats à réutiliser

**Date de revue :** 27 octobre 2026  
**Branche de travail :** `feat/v21310-star-portal-continuity-20261022`  
**Statut :** registre de candidats, pas une décision d'intégration ni une qualification runtime.

Ce registre complète `docs/COMPONENT-CATALOG-AND-REUSE.md`. Il distingue les composants issus des historiques AIOps et les projets open source externes. Un dépôt public n'est pas une preuve de compatibilité, de sécurité ou de fonctionnement dans notre architecture.

## 1. Règles d'intégration

- Conserver **un seul propriétaire de l'état Run/Incident/Decision** : Core et son schéma canonique.
- Garder Temporal/Worker propriétaire de l'orchestration durable ; n8n reste une frontière d'intégration, pas une seconde source d'état.
- Réutiliser d'abord par **adaptateur versionné**, contrat explicite, timeout borné, identité/provenance, état UNKNOWN en cas d'échec et tests isolés.
- Ne pas copier aveuglément des schémas, workflows, bases de données, fichiers de configuration, secrets ou artefacts de runtime historiques.
- Avant tout code tiers : vérifier licence au niveau du dépôt et des dépendances, version/tag exact, maintenance, vulnérabilités, SBOM, dépendances transitives, modèle de sécurité et coût d'exploitation. Conserver les notices/licences si du code est incorporé.
- Pas de déploiement ni d'appel LIVE pendant cette phase de sélection. Aucun candidat ne peut contourner Policy, HITL, PC11K5/fencing, journal append-only ou contrôles de provenance.

## 2. Candidats historiques AIOps v1 / V145 / V8

Les noms de dossiers et références ci-dessous proviennent des inventaires et comptes rendus historiques. Ils constituent des **pistes de récupération** ; les contenus exacts, les révisions, les dépendances et les tests doivent être revalidés dans les archives ou répertoires locaux avant de reprendre du code.

| Candidat historique | Capacité potentielle | Usage cible dans AIOps 2.0 | Priorité | État / action obligatoire |
|---|---|---|---|---|
| `v145-d4.57-evidence-acquisition` | Adaptateurs d'acquisition de preuves | Collecteurs en lecture seule pour stockage/SAN, monitoring, ITSM | P0 | Inventorier les connecteurs, auth, timeouts, fraîcheur et provenance ; aucune source n'est présumée fonctionnelle |
| `v145-d4.55-evidence-fusion` | Fusion multi-source | Dédupliquer et corréler les éléments de preuve avant Analyst/Critic | P0 | Vérifier les règles de conflit, traçabilité des sources et déterminisme |
| `v145-d4.56-evidence-matrix` | Matrice preuves/hypothèses | Read model expliquant hypothèses soutenues, contredites et inconnues | P0 | Vérifier scoring et cas manquants/contradictoires ; ne pas en faire un autorisateur de remédiation |
| `v145-d4.59-evidence-enrichment` | Enrichissement contextuel | Joindre CMDB, dépendances et runbooks sans écraser l'origine de la preuve | P1 | Conserver l'identifiant source, l'horodatage et la fraîcheur |
| `v145-d4.60-semantic-evidence-engine` | Recherche/matching sémantique | Aide au rapprochement d'incidents et de symptômes | P1 | Comparer à RAG actuel ; tests de pertinence, citations et prompt injection |
| `v145-d4.58-evidence-decision-adapter` | Traduction preuves → contrat décision | Adaptateur vers les contrats Run/Analysis/Critique actuels | P0 | Vérifier compatibilité des schémas et rejeter les champs implicites |
| `v145-d4.54-decision-intelligence` et `v145-d4.61-decision-intelligence` | Diagnostic/decision intelligence | Idées, règles ou code réutilisables pour Analyst/Critic | P1 | Comparer les deux versions et leurs consommateurs ; éviter le double moteur |
| `v145-functional-bridge` | Pont fonctionnel/API | Adaptateur de compatibilité temporaire entre modules | P1 | Examiner auth, routes, ownership et erreurs ; ne pas exposer directement à l'extérieur |
| `v145-functional-read-model` | Agrégation de statut | Vue unifiée portail/NOC, avec fraîcheur et états UNKNOWN | P0 | Séparer strictement lecture et état canonique ; éliminer cache périmé trompeur |
| `v145-decision-cockpit` | Cockpit de décision / UI | Concepts UX ou composants utiles au portail actuel | P2 | Comparer au portail courant ; ne réintégrer que des éléments utiles et testables |
| `v145-functional-orchestrator` | Orchestration fonctionnelle supposée | Éventuels patrons de séquencement | P2 / UNKNOWN | Inventaire antérieur trop faible (aucun fichier exploitable identifié) ; ne pas supposer qu'un module existe |
| AIOps v1 `/home/aiops/aiops-v1` — incidents, épisodes/relations, déduplication d'événements | Corrélation et modèle d'incident | Normalisation, corrélation et regroupement d'alertes | P0 | Mapper vers Incident/Run canonique ; tests de doublons, ordre d'arrivée, horodatage et rejeu |
| AIOps v1 — CMDB objets/relations | Topologie et dépendances | Enrichissement d'impact SAN → services métier | P0 | Valider source de vérité, fraîcheur, liens et conflits avec GLPI |
| AIOps v1 — audit/live activity/state history | Audit et historique | Historique append-only et enquête post-incident | P0 | Comparer à l'event ledger actuel ; préserver intégrité et ordre |
| AIOps v1 — knowledge documents/chunks | Corpus documentaire | Import des runbooks, incidents résolus, correctifs et articles fournisseur | P1 | Vérifier provenance, droits d'accès, version et suppression/retrait d'une source |
| AIOps v1 — remediation_runs | Historique de remédiation | Référentiel d'analyse des remédiations passées, pas moteur LIVE | P1 | Distinguer proposée/approuvée/exécutée/vérifiée ; ne jamais réutiliser un historique comme preuve d'autorisation |
| AIOps v1 — workflows n8n et dépendances | Intégration et notification | Réutiliser les workflows métier après audit | P1 | Exporter/inspecter sans secrets, inventorier credentials/IDs et tester dans n8n isolé |
| V8 R2 final2/final3, CLEAN R3, R6, R6 fix1/fix3, V8 rebuild | Kits/déploiements historiques | Récupération de code/configuration/tests manquants | P1 | Comparer les manifestes et diffs ; ne pas restaurer un stack entier sans preuve de compatibilité |
| Références historiques `12cc116`, `cf09ec3`, `4ce97f9`, `b870f48` | Baselines/intelligence/Worker | Rechercher les corrections ou contrats utiles à cherry-pick/adaptation | P0 | Reconstituer repo, branche, SHA complet, diff et tests ; les mentions courtes ne suffisent pas pour cherry-pick |
| PR historique #17 / branche `feature/r33-schema-reconciliation-2026-10-19` | `tools/schema_reconcile.py`, fingerprint/export/compare de schéma, tests et rapport | Audit de compatibilité de schéma en lecture seule | P0 | Reprendre l'outil si encore disponible ; son CI historique ne prouve pas la compatibilité des données de production |

**Priorité P0 = examiner en premier**, pas intégrer sans contrôle. Les anciens composants V145 sont à ce stade des candidats nommés, pas des modules validés.

## 3. Projets open source externes à évaluer

Les liens pointent vers les dépôts amont. Le tableau recommande d'abord l'usage de l'API, du protocole ou d'un adaptateur ; il ne recommande pas de forker ces projets ni de les embarquer tous dans le runtime.

| Projet amont | Usage possible | Décision provisoire | Garde-fous / qualification |
|---|---|---|---|
| [OpenTelemetry Collector](https://github.com/open-telemetry/opentelemetry-collector) | Collecte et export unifiés de métriques, logs et traces depuis les adaptateurs | **Candidat P0** pour réduire les collecteurs ad hoc | POC sur réseau isolé ; tester les receivers/exporters réellement requis, redaction, cardinalité, rétention et coût. Licence amont annoncée Apache-2.0 ; revalider au tag choisi |
| [Temporal](https://github.com/temporalio/temporal) + [SDK Python](https://github.com/temporalio/sdk-python) | Orchestration durable, retries, reprise et replay | **Conserver le choix actuel**, pas ajouter un deuxième moteur | Réutiliser les SDK/samples officiels ; tester workflow replay, compatibilité des workers et versions ; aucune migration de workflow sans plan |
| [LangGraph](https://github.com/langchain-ai/langgraph) | Graphe d'étapes d'agents avec état et HITL | **Alternative expérimentale uniquement** pour un sous-flux Analyst/Critic/RAG | Ne pas remplacer Temporal/Core par un second moteur. POC comparatif offline, licence et dépendances vérifiées avant décision |
| [Haystack](https://github.com/deepset-ai/haystack) | Pipelines RAG, retrieval, ranking, citations et évaluation | **Candidat P1** si le RAG actuel est incomplet | Comparer à l'implémentation existante avant d'ajouter une dépendance ; tester précision, rappel, fraîcheur, ACL, injection et citations ; dépôt annonce Apache-2.0, à confirmer au tag |
| [GLPI](https://github.com/glpi-project/glpi) et [GLPI Agent](https://github.com/glpi-project/glpi-agent) | ITSM/CMDB, inventaire et workflow opérateur | **S'appuyer sur les interfaces officielles**, pas réimplémenter GLPI | API/auth, droits, mapping d'objets et idempotence ; distinguer ticket de test et ticket réel. GLPI et Agent ont des licences différentes : vérifier chaque dépôt/version |
| [n8n](https://github.com/n8n-io/n8n) | Connecteurs et automatisations d'intégration | **Garder comme frontière**, pas comme source d'état AIOps | Vérifier la licence exacte et les conditions d'utilisation de la version déployée ; credential isolation, webhook signatures, retries, déduplication et export sans secrets |
| [Prometheus](https://github.com/prometheus/prometheus) | Métriques, règles et alertes | **Conserver l'intégration via API/PromQL** | Tester disponibilité, fraîcheur, labels, cardinalité, règles et corrélation incident ; ne pas coder en dur les résultats d'une fixture |
| [Alertmanager](https://github.com/prometheus/alertmanager) | Groupement, routage et inhibition d'alertes | **Candidat P0 d'intégration lecture seule** | Vérifier URL depuis le réseau réel, auth, silences, groupes et freshness ; ne modifier aucune règle ni silence pendant le diagnostic |
| [Grafana](https://github.com/grafana/grafana) | Dashboards, visualisation de métriques et explorabilité | **Intégrer par liens/API et captures de preuve** | Vérifier les permissions des service accounts, éviter les tokens dans les URLs, capturer le dashboard réel avec timestamp et source |
| [Qdrant](https://github.com/qdrant/qdrant) | Stockage vectoriel pour recherche sémantique/RAG | **Candidat P2**, seulement si le stockage actuel ne suffit pas | Mesurer le bénéfice contre l'index existant ; ACL/tenants, sauvegarde, suppressions, provenance et versionnement des embeddings |
| [AWX](https://github.com/ansible/awx) | Exécution d'automatisations Ansible contrôlées | **Ne pas retenir comme dépendance P0** ; option future pour actions HITL approuvées | Le dépôt amont signale une pause des releases pendant une refonte ; vérifier l'état actuel, les versions, la maintenance et les exigences opérationnelles avant tout choix |
| [OpenTelemetry Collector Contrib](https://github.com/open-telemetry/opentelemetry-collector-contrib) | Receivers/exporters additionnels | **Extension conditionnelle** du candidat OTel | Évaluer chaque plugin individuellement : surface d'attaque, dépendances, maintenance, licence et besoin réel |

### Pourquoi cette sélection

- **Réduire les lacunes de preuve et d'observabilité d'abord** : OpenTelemetry + contrats d'adaptateurs read-only.
- **Rendre le scénario métier fiable ensuite** : corrélation historique + CMDB/GLPI + NOC/Prometheus, avec IDs et fraîcheur.
- **Améliorer le raisonnement sans double orchestration** : comparer Haystack/LangGraph au pipeline Analyst/Critic existant sur un jeu holdout.
- **Ne pas ajouter une base vectorielle ou un moteur d'automatisation par effet de mode** : Qdrant/AWX restent conditionnels, pas des prérequis.

## 4. Ordre de travail proposé

1. **Récupération historique en lecture seule** : retrouver archives et révisions exactes ; générer inventaire fichier/hash/licence/tests, sans exécuter d'anciens scripts.
2. **Audit du code candidat** : entrées, contrats, dépendances, autorité d'état, réseau, credentials, données, tests et risques.
3. **Comparer avec le code actuel** : fonctions communes, écarts, chemins morts, contrats en conflit, coût de maintenance.
4. **Choisir par ADR** : réutiliser inchangé / adapter / remplacer / écarter / inconnu, avec justification.
5. **Prototype isolé** : données synthétiques, faux endpoints, permissions minimales et sorties reproductibles.
6. **Qualification** : tests unitaires/contrats, sécurité, panne/timeouts, replay, performances et rapport rattaché au SHA.
7. **Intégration de branche** : petit changement ciblé, CI verte sur le commit exact, mise à jour du catalogue et du registre de décision.
8. **Déploiement éventuel** : seulement après approbation explicite, préflight, sauvegarde vérifiée et rollback documenté.

## 5. Critères de sortie d'un candidat

Aucun candidat ne passe à « intégré et qualifié » tant que le registre ne contient pas : dépôt/source et commit exact, licence, propriétaire, diff, contrat, tests exécutés avec URL/artefact, SBOM ou inventaire des dépendances, résultat de sécurité, comportement en panne, décision ADR, mode de retour arrière et preuve séparant synthétique/live.

**État initial de ce registre :** tous les candidats ci-dessus sont « À AUDITER » ou « CANDIDAT CONDITIONNEL ». Cette documentation ne prétend pas qu'ils ont été téléchargés, compilés, exécutés ou intégrés dans cette session.
