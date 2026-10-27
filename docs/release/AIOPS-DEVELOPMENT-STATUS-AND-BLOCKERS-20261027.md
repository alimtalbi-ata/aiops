# AIOps 2.0 — État d'avancement, reste à développer et blocages

**Date de l'état des lieux :** 27 octobre 2026  
**Dépôt :** `alimtalbi-ata/aiops`  
**Branche de travail :** `feat/v21310-star-portal-continuity-20261022`  
**Pull request :** [#36 — brouillon](https://github.com/alimtalbi-ata/aiops/pull/36)  
**Nature du document :** état documentaire à partir du code et des documents de cette branche. Ce n'est pas une attestation du runtime Debian.

## 1. Résumé exécutif

AIOps 2.0 possède une base de reconstruction structurée : Core et contrats de décision, orchestration Temporal/Worker, adaptateurs Analyst/Critic, Policy Gate fail-closed, migrations/ledger, kit de déploiement, portail, modèles de lecture, scénarios synthétiques et tests de qualification. Le dépôt contient également des travaux d'intégration et de sécurité du portail.

**La plateforme complète n'est pas qualifiée de bout en bout sur le système cible.** Le principal écart est la différence entre des composants ou adaptateurs présents dans le dépôt, des tests synthétiques réussis à un commit précis, et des connexions métier/authentifiées réellement observées sur Debian. La matrice des routes du portail confirme que plusieurs familles produit ne sont pas raccordées par le portail source actuellement examiné.

**État CI de cette branche : NON CONFIRMÉ au moment de cette revue.** La consultation du connecteur GitHub n'a retourné aucun run associé aux derniers commits consultés. Cela ne signifie pas nécessairement qu'aucun workflow n'a tourné ; cela signifie que nous ne disposons pas ici d'une preuve de statut pour ce HEAD. Aucun PASS récent n'est inventé.

## 2. Légende des états

- **PRÉSENT — source** : code ou configuration repéré dans le dépôt ; ne prouve pas que le service fonctionne.
- **TESTÉ — isolé/synthétique** : un test vérifie le contrat dans le périmètre déclaré ; ne prouve pas le runtime cible.
- **PASS — CI commit précis** : seulement si un run lié au SHA et ses résultats sont disponibles.
- **NON QUALIFIÉ** : tests ou preuve runtime nécessaires non disponibles.
- **BLOQUÉ** : dépendance, risque ou intégration empêche de satisfaire le critère d'acceptation.
- **UNKNOWN** : preuves insuffisantes ; ne pas transformer en PASS.

## 3. Matrice de l'avancement

| Domaine | État connu au 27/10/2026 | Ce qui existe | Reste à développer / prouver |
|---|---|---|---|
| Core, états Run et contrats | Base source présente ; CI courante de PR non confirmée | API/Core, versionnement optimiste/idempotence décrits, ledger de décision et migrations | Rejouer toutes les gates sur le HEAD courant ; valider les transitions et les erreurs en E2E isolé |
| Temporal et Worker | E2E déterministe déjà documenté comme qualifié dans un jalon antérieur ; état du HEAD courant non confirmé | Orchestration durable et Worker, contrats d'événements/étapes | Réessayer timeout/retry, worker restart, idempotence, replay, concurrence/fencing et états partiels sur le HEAD actuel |
| Analyst/Critic et LLM | Contrats/adaptateur source présents ; vrai modèle non qualifié | API compatible OpenAI, schémas, références de preuves, garde-fous et évaluation synthétique documentés | Exécuter contre l'endpoint réel DGX/modèle configuré ; jeu de validation tenu à l'écart, latence, abstention, grounding, calibration et erreurs |
| Policy / sécurité des effets | Garde-fous conservateurs présents dans le projet | Policy fail-closed, séparation proposition/approbation/effet/vérification ; LIVE désactivé | Tests E2E d'approbation expirée/dupliquée, altération de hash, fencing, effet partiel et réconciliation indépendante |
| Portail / cockpit | Pages et handlers source présents ; expérience/runtime cible non qualifiés | Dashboard, runs, timeline, Twin, Policy, Copilot, Demo Studio, pages synthétiques | Connecter les écrans aux vrais read models ; états chargement/erreur/UNKNOWN, navigation, preuves visibles, captures authentiques et recette navigateur |
| Authentification portail | Bootstrap durci dans la branche | Bearer dédié `AIOPS_PORTAL_READ_TOKEN` sur `GET /api/portal/bootstrap`, 401/503, génération/migration de secret et tests source | Protection globale via SSO/proxy : le HTML, `/api/copilot` et d'autres APIs ne sont pas globalement protégés par ce seul changement ; qualification runtime des identités |
| Core/Twin via bootstrap | Adaptateurs HTTP source présents | Lectures bornées, sans retry, dégradation partielle vers UNKNOWN | Vérifier DNS/réseau/TLS/jetons, disponibilité, fraîcheur et autorisation sur environnement d'intégration ; aucun test ASGI ne prouve la connexion Debian |
| NOC / Checkmk / Thruk | Adaptateur NOC séparé présent, mais non monté dans le portail examiné | Contrat de read model et tests synthétiques existent | Monter le bon routeur, relier fournisseur authentifié en lecture seule, valider fraîcheur, erreurs et corrélation ; distinguer inventaire statique de données live |
| Grafana / Prometheus / Alertmanager | Certaines probes/outils ont existé dans des audits précédents ; état courant non revalidé | Configurations et familles d'intégration dans le dépôt | Refaire un audit read-only depuis le réseau exact des conteneurs ; résoudre les destinations injoignables précédemment observées pour Alertmanager/Loki ; prouver les données remontées et leur fraîcheur |
| GLPI / CMDB / HITL | Intégration portail réelle non prouvée | Schémas/intentions d'intégration et fixtures ACME/GLPI synthétiques | Connecteur lecture/écriture métier séparé, ticket réel avec IDs/horodatage/provenance, approbation HITL et reprise idempotente ; aucune écriture en production pendant la qualification |
| n8n | Connexion portail et passage de workflow E2E non prouvés | Orchestration d'intégration documentée et références à des workflows | Import/activation contrôlée en environnement isolé, authentification, identités d'événements, passage 02→03, reprises et captures d'exécution authentiques |
| RAG / base de connaissances | Implémentation et intégration complète non qualifiées | Plan d'architecture et candidats historiques v1/V145 recensés | Connecteurs incidents/problèmes/fixes/wiki/patches, citations, contrôle d'accès, fraîcheur, tests de pertinence et protection contre prompt injection |
| Digital Twin / ACME | Fixtures et scénario narratif synthétiques présents | Modèle d'impact déterministe local, écran de fixture et récit SAN/Payments | Calibrer dépendances et données ; relier l'incident ACME SAN P1 à Payments P2 via preuves backend réelles ; ne pas confondre SIM-GLPI/horloge fixe avec un ticket réel |
| Evidence Center / captures | Contrats et pages de démonstration présents, mais preuves runtime manquantes | Références de preuve, manifests et gates STAR dans le dépôt | Acquisition des captures authentiques, SHA-256, horodatage, run_id/incident_id/ticket_id, source, identité, fraîcheur et replay déterministe ; neuf checkpoints réels encore à qualifier selon le relevé antérieur |
| Kit cumulatif / release | Scripts de packaging et de vérification présents | ZIP cumulatif, manifeste/checksums, scripts de qualification documentés | Reproduire le kit depuis le HEAD courant, vérifier ZIP + SHA-256 + manifeste, prouver absence de secrets, joindre les rapports de ce même SHA et tester l'extraction propre |
| Déploiement Debian / port unique | NON QUALIFIÉ | Port cible demandé historiquement : `10.79.94.202:17777`; script/status/read-only runbooks | Vérifier la provenance Git/image/config réellement déployée, SSO, ports, healthchecks et intégrations sur l'environnement autorisé ; aucune opération serveur n'a été faite dans cette session |
| Historique v1/V145 | Inventaire partiel / candidats | Plusieurs répertoires et capacités candidates identifiés | Audit read-only complet du code, contrats, dépendances, tests et propriétaires ; décision explicite réutiliser/adapter/remplacer/retirer par module |
| Quatre cycles CI | Fichiers créés dans la branche de PR ; exécution non confirmée | Quatre workflows cron `00/12/24/36` UTC avec `workflow_dispatch`, permissions de lecture et concurrence séparée | Exécuter manuellement les workflows, corriger les chemins/dépendances manquants, vérifier leurs logs et activer le schedule après fusion approuvée. GitHub schedule ne s'exécute que depuis la branche par défaut. Ce sont des workflows de test, pas quatre agents de développement autonomes |

## 4. Blocages prioritaires

### B0 — Absence de preuve intégrée sur le HEAD courant
**Impact : critique.** Les workflows de cycles viennent d'être ajoutés et aucun run associé au dernier commit n'a été retourné par le connecteur lors de cette revue. Les résultats historiques ne qualifient pas automatiquement le code modifié depuis.

**Déblocage :** déclencher les workflows disponibles via `workflow_dispatch` après vérification de leur présence sur une branche accessible ; relever SHA, URL du run, jobs, artefacts, résultats et logs. Corriger les échecs avant d'étiqueter PASS.

### B1 — Connectivité métier et intégration du portail
**Impact : critique pour la démo utilisateur.** Le registre statique des routes ne prouve pas qu'un backend est connecté. L'inventaire source indique que GLPI/CMDB, n8n, Grafana, Prometheus, Alertmanager, Checkmk, Thruk, Temporal API, DGX Analyst/Critic et RAG ne sont pas directement raccordés par les routeurs du portail examinés. Le routeur NOC dédié est séparé et non inclus par le portail examiné.

**Déblocage :** définir des read models versionnés et des adaptateurs authentifiés ; monter les routeurs réellement requis ; tests contractuels avec faux serveurs puis tests d'intégration read-only dans le réseau isolé ; chaque source doit exposer identité, fraîcheur, disponibilité et provenance.

### B2 — Absence de recette E2E authentique ACME SAN P1 → Payments P2
**Impact : critique pour la démonstration de valeur.** Les fixtures sont explicitement synthétiques et ne démontrent ni un ticket GLPI réel, ni une exécution n8n réelle, ni les captures réelles des systèmes.

**Déblocage :** exécuter le scénario sur un environnement d'intégration isolé, collecter les neuf checkpoints et identifiants corrélés, calculer les empreintes, vérifier le replay déterministe et préserver la distinction SIMULATED/UNATTESTED/LIVE.

### B3 — Vrai modèle et RAG non qualifiés
**Impact : élevé pour la valeur AIOps.** Une évaluation avec fournisseur déterministe ou fixture synthétique ne démontre pas la qualité du DGX/LLM réel.

**Déblocage :** vérifier l'endpoint et le modèle configurés, exécuter un jeu holdout/adversarial versionné, mesurer latence, grounding, sévérité, abstention, contradictions et prompt injection ; connecter RAG avec sources et citations contrôlées. Aucun accès secret ne doit être commité.

### B4 — Sécurité globale et identité de bout en bout
**Impact : élevé.** Le jeton de bootstrap ne sécurise pas le portail entier. L'identité opérateur, le proxy/SSO, les scopes et la provenance d'action ne sont pas qualifiés runtime.

**Déblocage :** décider et documenter la frontière d'authentification globale ; tester routes HTML/API, expiration, refus, séparation des rôles et journaux expurgés. Pas d'exposition publique avant cette qualification.

### B5 — Provenance du déploiement et réversibilité
**Impact : élevé.** La présence d'un dépôt ou de conteneurs ne prouve pas que le runtime est issu du commit attendu. Un audit précédent indiquait la provenance Git/image/config comme non vérifiée.

**Déblocage :** collecte strictement read-only de la provenance (SHA Git, digest d'image, configuration non secrète, projet Compose, ports, volumes), puis backup/restore vérifié avant toute proposition de changement. Aucun redémarrage ni migration dans le cadre de ce document.

### B6 — Cadence horaire pas encore active
**Impact : moyen.** Les quatre workflows sont sur la branche de PR. GitHub n'exécute les événements planifiés que depuis la branche par défaut ; la PR est encore draft et n'est pas fusionnée. Quatre cycles aux minutes 00,12,24,36 ne donnent pas un espacement constant sur 60 minutes : il y a 24 minutes de 36 à 00.

**Déblocage :** d'abord exécuter/valider les workflows à la demande ; obtenir revue humaine ; fusionner uniquement après approbation ; si un intervalle constant de 12 minutes est réellement requis, prévoir cinq déclenchements par heure (00,12,24,36,48) plutôt que quatre. Aucun merge automatique.

## 5. Plan d'action ordonné

| Priorité | Action | Critère de sortie vérifiable |
|---|---|---|
| P0 | Vérifier les quatre workflows CI et tous les tests ciblés sur le SHA courant | Run URL + SHA exact + tous jobs PASS ou blocages consignés |
| P0 | Construire une carte de connectivité read-only par service depuis l'environnement isolé | Pour chaque backend : DNS/réseau/TLS/auth/endpoint/fraîcheur avec preuve et sans fuite de secret |
| P0 | Raccorder le portail au vrai read model NOC et aux composants prioritaires | Routes incluses, contrats versionnés, tests d'intégration et états UNKNOWN corrects |
| P1 | Réaliser le scénario d'intégration ACME SAN P1 → Payments P2 | IDs corrélés, preuves authentiques, neuf checkpoints, hashes, timeline et replay déterministe |
| P1 | Qualifier Analyst/Critic sur le vrai endpoint et relier RAG | Rapport holdout versionné, métriques, latence et provenance ; aucun effet d'action déclenché |
| P1 | Qualifier auth globale et rôles | Tests de refus et d'accès pour pages/API, SSO/proxy et audit sans secrets |
| P1 | Vérifier la provenance du déploiement et le plan de récupération | SHA/digests/config non secrète vérifiés, sauvegarde/restauration démontrée avant tout changement |
| P2 | Audit de réutilisation historique v1/V145 | Matrice module par module et décisions sourcées |
| P2 | Produire le kit cumulatif et le dossier de preuve | ZIP, SHA-256, manifeste vérifié, rapport CI du même SHA et instructions propres |

## 6. Règles d'acceptation des preuves

Chaque ligne de statut doit porter, quand disponible : date UTC, commit SHA, URL CI, nom de job, commande exacte, résultat, artefact, source de données et limite connue. Les états possibles sont PASS, FAIL, NOT RUN, BLOCKED ou UNKNOWN. Pas de statut « opérationnel » sur la seule base d'un écran, d'une route, d'un conteneur déclaré, d'une fixture, d'un fichier présent ou d'un test ancien.

Les captures d'écran sont classées comme :
1. **RÉELLES — runtime attesté** : prises sur l'environnement ciblé, identités et horodatage corrélés, provenance et hash validés.
2. **SYNTHÉTIQUES** : fixture locale ou navigateur de test.
3. **SIMULÉES / REPLAY** : scénario rejoué sans action live.
4. **NON ATTESTÉES** : origine ou intégrité insuffisamment prouvée.

## 7. Contraintes de changement

- Pas d'accès/modification production, pas de redémarrage/recréation de conteneur, pas de migration ni écriture backend sans approbation explicite, préflight et rollback.
- Pas de fusion automatique de la PR #36.
- Pas de remédiation LIVE ; les propositions restent consultatives.
- Pas de secrets, `.env`, export client ou logs privés dans Git, ZIP ou captures.
- Les cycles CI doivent rester isolés, avec permissions minimales et artefacts non sensibles.
- Les horaires GitHub sont en UTC et soumis aux délais de file d'attente.

## 8. Mise à jour obligatoire

À chaque cycle significatif, mettre à jour ce document et `docs/PROJECT-CONTINUITY.md` avec :
- SHA et PR ;
- tests réellement exécutés et URL des runs ;
- nouveaux éléments terminés ;
- blocages levés/nouveaux ;
- prochaines actions et critères de sortie ;
- preuve runtime distincte de la preuve synthétique.

Ne jamais remplacer les limites de ce document par une affirmation de succès sans nouvelle preuve.
