# AIOPS2 — HANDOVER / CONTINUITÉ OPÉRATIONNELLE

> **Point de reprise prioritaire.** Dernière actualisation : 2026-11-10 (coordination des tâches UI horaires).  
> Dépôt : https://github.com/alimtalbi-ata/aiops  
> Rapport central : PR #545 — https://github.com/alimtalbi-ata/aiops/pull/545  
> **Ce fichier est versionné sur la branche de la PR #545, pas encore sur `main`.** Vérifier l'état GitHub actuel avant toute action.

## 1. Objectif utilisateur — NE PAS PERDRE

**Auditer, sélectionner, consolider et intégrer les développements récents les plus utiles afin de faire évoluer la plateforme AIOPS2 existante déjà installée sur Debian.** Ne pas remplacer aveuglément l'existant par une reconstruction vierge. Les travaux d'installation isolée servent à qualifier et sécuriser une évolution contrôlée ; ils ne sont pas l'objectif métier principal.

Le travail autorisé à ce stade est **sur GitHub** (audit, code, tests, PR, documentation). L'utilisateur donne régulièrement « go » pour avancer par incréments. **« go » ne vaut pas autorisation de déployer ou d'intervenir sur Debian.**

## 2. Contraintes impératives / RELEASE HOLD

- Hôte Debian cible : `10.79.94.202`. **Aucun SSH, connexion, migration, redémarrage, déploiement, retrait legacy, modification des conteneurs, secrets ou volumes existants** avant approbation explicite, gates techniques et sécurité.
- **DNS interne Docker ENTRE APPLICATIONS AUTORISÉ** (résolution des noms de services via Docker, notamment `127.0.0.11`). **DNS vers des résolveurs HORS DU SERVEUR INTERDIT**. Il ne faut **pas** imposer des IP statiques ni interdire les noms de services. Vérifier qu'une requête inconnue n'est pas relayée par le résolveur Docker vers l'extérieur.
- Mode d'installation/qualification **hors ligne**, images préchargées, sans pull/build réseau ; ports publiés seulement sur `127.0.0.1` ; ressources séparées ; sauvegarde/restauration et rollback démontrés.
- P0 sécurité #535 : un ancien exemple n8n contenait un credential et un chemin LIVE risqué. PR #536 neutralise le template selon inspection précédente, **mais révocation/rotation effective, audit des utilisations/copies/historique et revue sécurité indépendante ne sont pas prouvés**. Ne jamais publier le secret.
- Revue indépendante, CI du commit courant, tests intégrés, autorisation de changement : indispensables avant fusion/promotion. **Ne pas confondre CI historique verte et CI de la tête actuelle.**

## 3. Cartographie GitHub — vérifiée au 2026-11-10

| PR / issue | Objet | Base PR observée | Statut / attention |
| --- | --- | --- | --- |
| #515 | Core : fail-closed scénario persistant corrompu | `agent/core/499-gate-required-evidence-reconcile-20261110` | Draft, branche empilée |
| #516 | Worker : bornage métadonnées UTF-8 FS147 | `agent/worker/457-fs147-action-binding-20261110` | Draft, branche empilée |
| #517 | Twin : provenance imbriquée SAN/FS147 | `feat/fs147-twin-adapter-qualification-20261108` | Draft, branche empilée |
| #529 | PostgreSQL DR : conteneur PG16 pour restauration jetable | `fix/ci-postgres16-client-dr-20261110` | Draft, branche empilée |
| #536 | n8n : exemple inerte et fail-closed | `ci/parallel-python-json-yaml-labs-20261110` | Draft ; ne clôt pas #535 |
| #541 | Portal : filtre des preuves contradictoires | `agent/portal/461-operational-timeout-20261110` | Draft, branche empilée |
| #544 | Portal : accessibilité historique Prometheus | `agent/portal/472-history-auth-denial-20261110` | Draft, branche empilée |
| #547 | Portal : états timeout/annulation | `agent/portal/461-integrate-timeout-redaction-20261110` | Draft, branche empilée |
| #545 | Rapport central / plan de qualification | `main` | Draft ; **présent handover ici** |
| #548 | Plan de changement Debian | à revérifier | Document de préparation |
| #549 | Compose/installer Debian isolé | `main` | Draft ; ne pas exécuter sans gates |
| #552 | Réparer n8n↔PostgreSQL, simulator↔core ; images explicites | branche de #549 | Draft ; dépend de #549 |
| #535 | P0 sécurité credential n8n | issue | Bloquant |
| #553 | DNS sortant hors serveur | issue | Périmètre corrigé, qualification attendue |

**Attention aux branches empilées** : les PR fonctionnelles ne sont pas toutes directement basées sur `main`. Analyser les ancêtres et les différences cumulées avant de préparer une branche d'intégration. Ne pas fusionner les huit PR en bloc.

## 4. Travail effectivement réalisé dans les derniers échanges

- Audit des branches de base et des fichiers changés des PR #515/#516/#517/#529/#536/#541/#544/#547/#549/#552.
- Matrice de sélection et ordre d'intégration : `docs/ops/AIOPS2-CONSOLIDATION-PR-20261110.md` (branche PR #545).
- PR #552 : correctifs des réseaux partagés n8n/PostgreSQL et simulator/core ; noms d'images explicites ; tests statiques ajoutés.
- Une interprétation **erronée** du DNS comme interdiction du DNS Docker interne avait entraîné un verrou temporaire dans l'installateur. **Verrou retiré** et test obsolète supprimé ; issue #553, documentation et commentaire d'audit rectifiés.
- `deploy/validate-isolated-network-plan.py` et ses tests ont été ajoutés sur #552 pendant cette fausse hypothèse : **outil optionnel, non requis pour la cible**. Décider de le supprimer pour limiter la dette et éviter de réintroduire une obligation d'IP statiques.
- Aucun merge, aucune qualification runtime globale et aucune intervention Debian dans ces échanges. Les runs CI des derniers commits #552 n'étaient pas visibles lors des consultations précédentes.

## 5. Stratégie de consolidation — ordre recommandé

1. **Sécurité** : comparer #536 à `main` et à ses ancêtres ; vérifier l'absence de credential et de chemin LIVE ; collecter hors GitHub les preuves de rotation/révocation et d'audit ; revue indépendante #535.
2. **Core + Worker + Twin** : lire les diffs et chaînes de bases de #515/#516/#517, sélectionner les durcissements fail-closed utiles et compatibles ; préparer une branche de consolidation à partir d'une base approuvée, avec tests transverses.
3. **Portal** : réconcilier #541/#544/#547 et leurs ancêtres ; éviter les régressions de sécurité, de timeout et d'accessibilité.
4. **DR** : qualifier #529 et ses dépendances ; exiger une restauration de test documentée.
5. **Déploiement isolé** : qualifier #549/#552, contrôle DNS sortant, images locales, loopback, connectivité, sauvegarde/rollback. Déploiement seulement après décision explicite.

## 5 bis. Coordination des 5 tâches planifiées UI / portail (mise à jour 2026-11-10)

**Contexte fourni par l'utilisateur** : cinq tâches ChatGPT actives, chacune programmée toutes les heures, travaillant en parallèle sur audit des régressions, design UX/UI, données/automatisations, frontend/recette et coordination. Leur état/schedule interne n'a **pas été revérifié via l'API des automatisations pendant cette intervention**. Les contributions suivantes ont été vérifiées **directement sur GitHub** :

| Flux | PR / commit de tête | Constat GitHub | Décision |
| --- | --- | --- | --- |
| Audit régressions | #538 `4615c05a3b1215e457ac92495387692f7c39c411` | Draft, base `main`; tests HTTP 404/405 et navigation superseded ; **1 workflow réussi** | Tests utiles, candidat indépendant à consolider |
| UX/UI | #541 `a4a8a5f918a1eb6ba32c15601ef97057a485d17c` | Draft ; base `agent/portal/461-operational-timeout-20261110` ; filtre de preuves | Conserver la protection, vérifier la chaîne des bases |
| Données/automatisations | #550 `9c3227195cda9957e1f6dfce59bb0215702e53d4` | Draft ; base exactement le head de #547 `52b15a6cc8bced70aa81a5559f2e69e98ea52357` ; `compare`: **ahead 2 / behind 0** ; **4 workflows réussis** ; une revue COMMENTED par le propriétaire, **pas une approbation indépendante** | Regrouper avec #547. Le timeout passe d'une comparaison de chaîne d'erreur à un `Symbol` non falsifiable ; le transport ne peut plus forger TIMEOUT |
| Frontend/recette | #551 `31f735ae70d2b14831893254bdd11aa28ecf8c26` | Draft ; base exactement le head de #544 `865fea95469078adffa87a5738ffcfe03d2af1a6` ; `compare`: **ahead 2 / behind 0** ; **3 workflows réussis** | Regrouper avec #544. Corrige `aria-label` de l'historique Prometheus vide |
| Coordination générale | Synthèse sur #550 (information fournie) | Aucun merge ni déploiement autorisé | Utiliser PR #545 + ce handover comme relais inter-agents |

**Chevauchements confirmés :**
- #547 et #550 touchent tous deux `app/portal/components/operational_state.mjs` et ses tests ; chaîne ordonnée #547 → #550.
- #544 et #551 touchent tous deux `scripts/fs/fs1097_patch.py` ; chaîne ordonnée #544 → #551.
- #538 ajoute trois **fichiers de tests** et cible directement `main`; vérifier leur compatibilité avec la version effective du portail au moment du regroupement.
- #541 est sur une base d'une autre branche Portal ; analyser les interactions avec les autres changements UI au niveau des versions communes.
- Les informations du précédent chat évoquent un portail existant sur port `7777`, une recette candidate sur `17778` et cinq stacks Docker ; **ces faits sont seulement rapportés**, sans inspection du serveur dans cette session. Ne pas les présenter comme vérifiés en direct.

**Règles pour cinq tâches concurrentes :** attribuer un propriétaire par fichier/zone ; privilégier des branches et PR distinctes ; éviter les modifications simultanées sur la branche de coordination #545 ; fournir à chaque livraison le numéro PR, la base et le head SHA, les fichiers modifiés, les tests du head, la dépendance amont et les risques. Le coordinateur doit recomparer les heads GitHub avant consolidation : une tâche horaire peut actualiser une branche entre deux vérifications.

**Nouvelle priorité parallèle :** consolider le paquet Portal (#541, #547→#550, #544→#551, #538) avec des tests UX/sécurité communs pendant que l'audit Core/Worker/Twin progresse ; aucune fusion automatique.

## 6. Prochaine action concrète pour un nouvel agent

**Ne pas commencer par le déploiement Debian.** Commencer par récupérer l'état actuel des PR et les diffs/commits cumulés **#515, #516, #517** contre leurs bases et contre `main`. Construire une matrice « changement utile / dépendance / risque / test requis », puis créer une branche/PR de consolidation **uniquement si** les dépendances sont comprises et le périmètre testable. Garder les PR sources en Draft et ne rien fusionner automatiquement.

Après chaque incrément : mettre à jour ce handover (faits, SHA, décisions, résultats CI et prochaine action), la matrice de consolidation, puis laisser un commentaire de synthèse sur #545. Signaler clairement les tests non exécutés et les informations non prouvées.

## 7. Liens de reprise

- Rapport central : https://github.com/alimtalbi-ata/aiops/pull/545
- Matrice : https://github.com/alimtalbi-ata/aiops/blob/docs/debian-deployment-qualification-plan-20261110/docs/ops/AIOPS2-CONSOLIDATION-PR-20261110.md
- Plan Debian : https://github.com/alimtalbi-ata/aiops/pull/548
- Installateur isolé : https://github.com/alimtalbi-ata/aiops/pull/549
- Correctifs isolés : https://github.com/alimtalbi-ata/aiops/pull/552
- Sécurité : https://github.com/alimtalbi-ata/aiops/issues/535
- DNS hors serveur : https://github.com/alimtalbi-ata/aiops/issues/553

## 8. Règle de continuité

Ce document est le **journal de reprise**, pas une source de vérité immuable : relire les métadonnées GitHub, vérifier les SHA/CI/reviews au moment d'agir et dater les changements. Ne pas inscrire de secrets, d'identifiants sensibles ou de preuves d'accès dans le dépôt.
