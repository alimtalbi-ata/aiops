# AIOps 2.0 — État d'avancement, reste à développer et blocages

**Date de l'état des lieux :** 27 octobre 2026  
**Dépôt :** `alimtalbi-ata/aiops`  
**Branche de travail :** `feat/v21310-star-portal-continuity-20261022`  
**Pull request :** [#36 — brouillon](https://github.com/alimtalbi-ata/aiops/pull/36)  
**Nature du document :** état documentaire à partir du code et des documents de cette branche. Ce n'est pas une attestation du runtime Debian.

## 1. Résumé exécutif

AIOps 2.0 possède une base de reconstruction structurée : Core et contrats de décision, orchestration Temporal/Worker, adaptateurs Analyst/Critic, Policy Gate fail-closed, migrations/ledger, kit de déploiement, portail, modèles de lecture, scénarios synthétiques et tests de qualification. Le dépôt contient également des travaux d'intégration et de sécurité du portail.

**La plateforme complète n'est pas qualifiée de bout en bout sur le système cible.** Le principal écart est la différence entre des composants ou adaptateurs présents dans le dépôt, des tests synthétiques réussis à un commit précis, et des connexions métier/authentifiées réellement observées sur Debian. La matrice des routes du portail confirme que plusieurs familles produit ne sont pas raccordées par le portail source actuellement examiné.

**État CI de cette branche : EN ATTENTE / NON QUALIFIÉ au moment de cette revue.** La consultation la plus récente a retourné plusieurs runs de workflows PR en état `queued` pour le commit `3aa3a95006d834cf3b8e92ba063ebb0dd43776c6` (dont kit cumulatif, tests STAR, replay historique et NOC/RAG synthétique). Aucun de ces runs n'était indiqué comme terminé dans cette réponse. Ils ne prouvent donc ni PASS ni FAIL ; il faut récupérer leurs résultats et logs avant de conclure.

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


## 9. Candidate audit — new source review and implementation (27 October 2026)

The initial audit is recorded in [AIOPS-HISTORICAL-EVIDENCE-CANDIDATE-AUDIT-20261027.md](AIOPS-HISTORICAL-EVIDENCE-CANDIDATE-AUDIT-20261027.md). The named V145 source paths were not found in the checked GitHub branch trees; this does not prove absence from server/archives/other refs. Current source already includes evidence identity, freshness/quality guards, append-only ingestion contracts and an explicitly synthetic ACME read model.

A first generic read-only matrix has now been added:
- `app/shared/evidence_matrix.py`
- `tests/test_evidence_matrix.py`
- `.github/workflows/quality.yml` runs the new test file.

**State: code added, qualification pending.** Do not report PASS until CI logs for the exact resulting SHA are checked. No backend, server or production was accessed.

## 9. Registre des codes candidats réutilisables

Le catalogue dédié [AIOPS-CANDIDATE-CODE-REUSE-REGISTER-20261027.md](AIOPS-CANDIDATE-CODE-REUSE-REGISTER-20261027.md) référence :
- les candidats historiques v1/V145 (acquisition/fusion/matrice/enrichissement de preuves, décision intelligence, functional bridge/read model/cockpit, schémas et workflows) ;
- les lignes historiques V8 et les références de commits/PR à reconstituer ;
- les dépôts open source amont candidats (OpenTelemetry, Temporal/SDK, LangGraph, Haystack, GLPI/Agent, n8n, Prometheus, Alertmanager, Grafana, Qdrant, AWX) ;
- la priorité, la raison, les garde-fous, les contrôles de licence et les critères de sortie.

**État : registre de candidats seulement.** Aucun code tiers n'est déclaré téléchargé, intégré ou qualifié sur la seule base de cette liste. Chaque candidat doit être relié à un tag/commit exact, à sa licence, à des tests exécutés et à une décision ADR avant intégration.

## 8. Mise à jour obligatoire

À chaque cycle significatif, mettre à jour ce document et `docs/PROJECT-CONTINUITY.md` avec :
- SHA et PR ;
- tests réellement exécutés et URL des runs ;
- nouveaux éléments terminés ;
- blocages levés/nouveaux ;
- prochaines actions et critères de sortie ;
- preuve runtime distincte de la preuve synthétique.

Ne jamais remplacer les limites de ce document par une affirmation de succès sans nouvelle preuve.


## 10. Cycle 27 octobre — bootstrap borné et déduplication du patrimoine NOC

**État de référence de ce rapport : commit source `94036198818e0a50a3cbc77aa586d76a7bd4ad08`, PR #36 ouverte en draft.** Les résultats ci-dessous sont horodatés par les exécutions GitHub Actions ; ils ne qualifient pas le runtime Debian.

### Changement fonctionnel
- `app/portal/main.py` : pool partagé fixe de six workers pour les trois GET indépendants du bootstrap, au plus deux requêtes bootstrap simultanées ; une troisième est refusée rapidement par HTTP 503 `portal_bootstrap_capacity_exceeded`.
- `tests/test_portal_bootstrap_read_model.py` : test de saturation synthétique occupant les six workers, vérifiant le refus de surcharge puis la libération propre.
- Rollback source-only : revenir au commit parent de la modification de `app/portal/main.py` sur la branche de PR et relancer les suites offline. Aucun changement de déploiement ou de backend.

### Qualification exacte
- [Single-portal candidate kit — run 40535354678](https://github.com/alimtalbi-ata/aiops/actions/runs/40535354678) : PASS. Les 14 suites exécutées dans le job ont passé ; 176 tests comptés dans les sorties des suites, dont `test_bootstrap_rejects_excess_concurrent_requests_without_pool_growth`. Génération ZIP, `unzip -t`, comparaison au checkout épinglé et 81 sommes internes PASS.
- [AIOps quality gates — run 40535354734](https://github.com/alimtalbi-ata/aiops/actions/runs/40535354734) : PASS, six jobs terminés avec succès, dont runtime E2E sur stack CI isolée, build/qualité incluant les contrats Temporal, migrations PostgreSQL, upgrade du runner de migration, répétition DR MariaDB et release kit.
- [Historical ZIP source recovery — run 40535354677](https://github.com/alimtalbi-ata/aiops/actions/runs/40535354677) : PASS, qualification du mécanisme de récupération synthétique uniquement.
- [F20.13 checkpoint plan builder — run 40535354842](https://github.com/alimtalbi-ata/aiops/actions/runs/40535354842) : encore en cours au dernier relevé. [STAR Chromium read-only fixture qualification — run 40535354727](https://github.com/alimtalbi-ata/aiops/actions/runs/40535354727) : encore en cours. À ce relevé, 25/27 workflows étaient terminés avec succès, zéro échec observé et deux en cours.

### Récupération / déduplication
L'archive Library `AioOps-NOC-Offline-Browser-Evidence.zip` a été matérialisée dans un workspace isolé, CRC vérifié, puis chaque membre a été haché. Elle contient dix membres : trois PNG de rendus locaux hors ligne, des HTML et JSON ; aucun module Python ni adaptateur de service live. Les liaisons événement/capture sont déjà produites par `demo/noc_star_event_binding.py` et couvertes par `tests/test_noc_star_event_binding.py`. Décision : conserver l'inventaire/hash comme référence documentaire, ne pas réimporter le code ou les images et ne pas les promouvoir en preuve applicative. L'inventaire membre par membre figure dans `docs/release/AIOPS-PORTAL-ROUTE-INVENTORY-20261025.md`.

Le candidat ZIP du commit de référence a pour SHA-256 `1e8503990f41a4049e3d530de8f473d04869c50308b9604207808cd183d6c81f`, 82 membres, 78 sources embarquées, 638 entrées de source inventoriées et 20 routes non qualifiées. Ce kit est un sous-ensemble épinglé et **non déployable**, pas un installateur complet. Il n'intègre ni captures applicatives authentifiées ni secrets.

### Blocages inchangés
- Les octets originaux des archives privées Hybrid Replay V2.13.4/V2.13.6.1 et les fichiers complets `demo-multistack-capture.py` / `playwright-evidence-campaign-full.py` ne sont pas accessibles dans la Library de ce cycle. Les hashes historiques consignés ne remplacent pas les octets sources.
- Les 20 familles du registre ne sont pas qualifiées pour les connexions runtime ; l'authentification bootstrap ne protège pas globalement toutes les pages/APIs.
- Aucun E2E authentifié sur `:17777`, aucune sauvegarde/restauration de production vérifiée et aucune approbation de bascule. Production = NO-GO.
- Prochaine action : attendre et examiner les deux workflows STAR encore en cours, puis poursuivre l'E2E isolé de la cinématique ACME SAN P1 → Payments P2 avec captures exactes par application, identité et provenance fail-closed. Ne jamais convertir une fixture ou un hash local en attestation runtime.


## 11. Cycle 27 octobre — deadline globale bootstrap et kit cumulatif complet

**SHA de référence :** `61521a94c274026d9bf1e53d4990ccdb0411d57b` ; PR #36 ouverte en draft. Cette section complète les observations historiques précédentes ; elle ne les remplace pas et ne qualifie pas le runtime Debian.

### Changement fonctionnel livré

- `app/portal/main.py` : les trois lectures indépendantes Core/Twin utilisent maintenant une **deadline commune de 3 secondes** via `concurrent.futures.wait`. Une lecture encore pendante est rendue `UNKNOWN`, source `UPSTREAM_TIMEOUT`, code `READ_DEADLINE_EXCEEDED`; les autres sections restent visibles.
- Les deux créneaux bootstrap restent réservés jusqu'à la fin réelle des workers retardataires. Cela évite qu'un appelant qui a déjà reçu une réponse de timeout libère immédiatement sa capacité et accumule des tâches derrière un worker bloqué.
- `tests/test_portal_bootstrap_read_model.py` ajoute `test_shared_deadline_marks_stalled_sources_unknown_and_keeps_capacity_leased`, qui vérifie le timeout, l'état DEGRADED et le refus de surcharge tant que les workers retardataires ne sont pas terminés.
- `docs/release/AIOPS-PORTAL-ROUTE-INVENTORY-20261025.md` documente le contrat exact et la portée de cette protection.
- Rollback source-only : revert des commits `a48df18105de4b175bb538e7fdd44642eba98df4`, `049cc9a984a86a1199166d053f2d32efdcbc7057` et `61521a94c274026d9bf1e53d4990ccdb0411d57b` sur la branche PR, puis relancer les tests isolés. Aucun changement de runtime n'est requis.

### Qualification exacte sur le SHA de référence

- [Kit cumulatif — run 40544034897](https://github.com/alimtalbi-ata/aiops/actions/runs/40544034897) : PASS. Les 14 suites exécutées dans ce job ont toutes réussi, **177 tests** comptés dans les sorties, dont les 7 tests bootstrap et le nouveau cas de deadline partagée. Le ZIP a été construit depuis le SHA épinglé, contrôlé par `unzip -t`, puis comparé au checkout. Le manifeste interne a 81 entrées SHA-256 vérifiées.
- [AIOps quality gates — run 40544034983](https://github.com/alimtalbi-ata/aiops/actions/runs/40544034983) : PASS, les six jobs terminés avec succès, incluant runtime E2E sur stack CI isolée, contrats Temporal, build/qualité, migrations PostgreSQL, upgrade du runner de migration, répétition DR MariaDB et release kit.
- [Récupération ZIP historique — run 40544035087](https://github.com/alimtalbi-ata/aiops/actions/runs/40544035087) : PASS du mécanisme de récupération synthétique uniquement.
- [Plan de checkpoints F20.13 — run 40544035355](https://github.com/alimtalbi-ata/aiops/actions/runs/40544035355) : PASS des tests du générateur de plans hors ligne ; cela ne prouve pas que les écrans réels GLPI/n8n/Grafana ont été capturés.
- Au relevé du 27 octobre 2026 vers 16:48 UTC : 25/27 workflows terminés avec succès, zéro échec, deux en cours — [Chromium fixture read-only](https://github.com/alimtalbi-ata/aiops/actions/runs/40544037323) et [génération vidéo de démonstration](https://github.com/alimtalbi-ata/aiops/actions/runs/40544035081). Les deux résultats ne sont pas extrapolés.

### Récupération historique — constat limité et reproductible

- L'arbre Git récursif du SHA `61521a9…` contient 733 entrées et **aucun fichier archive** avec extension ZIP/TAR/GZ/7Z. Sous `recovery/legacy_v2134`, seuls `tools/assemble_hybrid.py` et `tools/audit_hybrid_dependencies.py` sont présents.
- Deux recherches simplifiées dans la Library accessible n'ont retrouvé ni l'archive originale Hybrid Replay V2.13.4, ni l'archive F20.13 Playwright, ni `tools/build_real_replay.py` / `tests/test_replay.py`.
- Ce résultat signifie « octets non disponibles dans les sources consultées pendant ce cycle », pas « fichier inexistant partout ». Les SHA historiques consignés ne sont pas utilisés pour reconstruire un fichier dont les octets ne sont pas accessibles.
- Le kit cumulatif est étendu pour embarquer ce rapport de blocages, le registre de réutilisation et l'audit des candidats historiques. Ces documents ne contiennent que des références et décisions de réutilisation ; ils ne déclarent aucun code tiers téléchargé ou qualifié.

### Limites inchangées

- Le bootstrap reste une lecture Core/Twin en lecture seule, avec provenance amont non attestée. Le jeton protège uniquement cette route, pas toutes les pages/API du portail.
- Les 20 familles de composants restent non qualifiées pour le runtime ; aucun E2E authentifié sur `:17777`, aucune capture applicative réelle ni attestation DGX/GLPI n'est établie.
- Production = NO-GO jusqu'à l'intégration runtime authentifiée, sauvegarde/rollback vérifiés et approbation explicite. Aucun accès ou changement Debian, nouveau port, écriture backend ou remédiation LIVE.


## Cycle update — signed NOC read-model seam (27 October 2026)

The existing portal now mounts GET /api/noc/runtime-state in the same ASGI process. It is an optional, authenticated-by-caller, read-only adapter for a configured upstream read-model endpoint. Upstream data is accepted only when the exact origin is allowlisted and both the response-body SHA-256 and HMAC-SHA256 signature verify. The route refuses redirects, limits reads to 256 KiB and three seconds, rejects duplicate JSON keys and stale timestamps, and redacts upstream failures.

This is a functional integration seam, not a Checkmk/Thruk connector. All upstream variables remain blank by default, so the route returns 503 until a trusted provider and credentials are provisioned. The output explicitly keeps runtime_attested=false, runtime_authenticated=false and live_remediation_authorized=false; screenshot bytes and GLPI ticket identity are not independently attested. Any 02→03 handoff claim is rejected because the canonical verifier is not yet embedded in the portal image.

Tests use only synthetic payloads and credentials. The cumulative candidate-kit allowlist and CI trigger now include the adapter, its tests and the contract document. No new port, service, production access, backend write or LIVE remediation is introduced.



NOC source preflight: optional configuration is now all-or-none. An unset source remains disabled and the endpoint returns 503; a partially configured source, short token/HMAC key, or endpoint-origin mismatch is rejected before any upstream request. The tests use disposable synthetic .env files only.

## Cycle 16 — correction CI NOC et état du kit (27 octobre 2026)

- HEAD inspecté avant correction : `00ae73d7c1952611ac482a88d8fd753313c1f8a2`; PR #36 ouverte, draft. La comparaison avec la branche de base `feat/v28-transactional-denial-fencing-20261020` indique 907 commits en avance, 0 en retard. Le dernier relevé PR après corrections indique `mergeable=true`; aucun merge/rebase n'a été exécuté.
- Première panne reproductible du kit (run [40553294440](https://github.com/alimtalbi-ata/aiops/actions/runs/40553294440)) : le test NOC attendait à tort l'absence de `runtime_authenticated`, alors que le contrat projette volontairement ce champ à `false`. Correction dans `tests/test_portal_noc_runtime_adapter.py` : l'assertion vérifie désormais explicitement `False`, y compris quand le fournisseur signé annonce `true`. Le contrat d'architecture précise cette non-attestation.
- La réexécution sur le HEAD intermédiaire a ensuite découvert un défaut de banc de test : `test_platform_registry_portal_route.py` utilisait `self.client` sans le créer. Correction : le cas crée un `TestClient(app)` local, comme les autres tests de cette classe.
- Le kit cumulatif a réussi sur le commit `886c07603ca9f00a5acc43ecc82932d798b60812`, run [40563466491](https://github.com/alimtalbi-ata/aiops/actions/runs/40563466491). Les suites ciblées, le préflight, la génération du ZIP, son contrôle ZIP et la vérification du checkout épinglé sont PASS. Candidat de ce HEAD : 89 membres vérifiés, inventaire de 642 sources, 20 familles de routes toujours non qualifiées, `production_qualified=false`; SHA-256 du ZIP intérieur `c09de46868610ebd033a61bbd76184c85849180f08ce856ecd610175473e7bb0`. Ce hash ne s'applique qu'à ce HEAD.
- Au dernier relevé du HEAD `886c076…` : 24 workflows réussis, 3 en cours, 0 échec. Les workflows encore actifs étaient les gates qualité, le rendu Chromium en lecture seule et la génération vidéo. Les résultats finaux de ces jobs doivent être relus avant la qualification globale.
- Routes effectivement montées par le portail existant : `GET /noc` (page statique locale), `GET /api/platform/components` (registre statique) et `GET /api/noc/runtime-state` (adaptateur de read model signé). Le pont NOC refuse la mise en cache pour succès/erreurs et exige le jeton de lecture portail. Sans configuration complète de la source amont, il répond 503 et ne contacte pas le fournisseur. La présence de route ne prouve pas une connexion runtime.
- Routes/familles restant non qualifiées : `/api/noc/state` demeure non montée ; les 20 composants du registre n'ont pas tous une route runtime attestée ni une connexion backend qualifiée. Aucun fournisseur Checkmk/Thruk réel, ticket GLPI réel, événement runtime authentifié ou capture F20.13 n'a été prouvé par ces tests.
- Recherche des originaux dans les fichiers Library et conversation connectés : aucun résultat exploitable pour les ZIP Hybrid Replay V2.13.4 et F20.13 Playwright lors de ce cycle. Cela décrit uniquement les sources indexées accessibles, pas l'inexistence d'une copie ailleurs. Aucun fragment n'a été promu au rang de module complet et aucune archive historique n'a été ajoutée artificiellement.
- Aucune modification de production, aucun port additionnel, redémarrage, écriture backend ou action LIVE. PR toujours draft ; NO-GO production tant que l'E2E authentifié sur runtime réel, le rollback vérifié et l'approbation de bascule manquent.


## Cycle 17 — Evidence Matrix : entrées malformées et classification précise (27 octobre 2026)

- Correctif fonctionnel dans `app/shared/evidence_matrix.py` : une collection d'évidences non-listes est désormais `BLOCKED_FOR_REVIEW` (et non `UNKNOWN` présenté comme une simple absence de données). Une collection d'hypothèses de mauvais type ou contenant des entrées non-objets ajoute une erreur explicite et bloque la revue au lieu de lever une exception ou de compter silencieusement des éléments ignorés.
- Correction de classification d'intégrité : les erreurs indexées sont associées à la position exacte et les identifiants dupliqués à l'identifiant exact. Un identifiant `E1` n'est donc plus marqué invalide par simple sous-chaîne d'une erreur `duplicate_evidence_id:E10`. Les doublons restent bloquants et leurs lignes restent `INVALID`.
- Tests de régression ajoutés dans `tests/test_evidence_matrix.py` : collection evidence non-list, hypothèses non-list, hypothèse non-objet et collision de préfixe E1/E10.
- Le workflow `.github/workflows/quality.yml` exécute déjà `test_evidence_matrix.py` ; aucun workflow redondant n'a été ajouté. Qualification du nouveau HEAD : **en attente** jusqu'à vérification des runs Actions associés au SHA final. Les commits code/test sont `e06681e8a7171a2fc8181e9648f88f2232f7f67f` et `b312923f71ddeacd9dde9a8d930f7236518ae528`.
- Le correctif n'accorde aucune autorité de décision ni d'action ; `action_authorized=false` reste invariant. Il ne connecte aucun backend et n'affirme aucune provenance runtime.
- Rollback source-only : revert des commits de ce cycle sur la branche PR, puis réexécuter `python -m unittest discover -s tests -p 'test_evidence_matrix.py' -v` et les gates qualité. Aucun déploiement ou changement de runtime requis.
- Aucun original Hybrid Replay/F20.13 nouveau n'a été récupéré dans les sources consultées durant ce cycle ; les octets manquants restent bloquants et ne sont pas reconstruits à partir de hashes ou de fragments.
