# AIOps V2.11.5 — Baseline de démonstration et reprise post-demo

Date de référence : 21 octobre 2026. Démonstration prévue le 22 octobre 2026.

## 1. Baseline vérifiée (preuves fournies depuis SRV-DEB-05)

- Branche : `feat/v28-transactional-denial-fencing-20261020`
- Dernier commit de baseline documentaire : `ddae0eeb9ec1390ca9babc6928d868ca0d653b03`.
- Policy V2.10.0–V2.10.7 : 33 tests regroupés PASS avec ResourceWarning traités comme erreurs.
- Policy V2.10.8 : 4 tests PASS.
- ACME Policy V2.10.9 : 3 tests PASS.
- Story portail V2.11.0 : 3 tests PASS.
- Préflight HTML/HTTP V2.11.1 : 2 tests et 7 points HTTP PASS.
- Inspection source V2.11.2 : 3 tests et 9 contrôles PASS.
- Chromium V2.11.3 : 10 étapes, reset, aucune requête d'écriture HTTP, PASS.
- Préflight répété à 2026-10-21T21:15Z : 7/7 HTTP PASS et Chromium PASS.

**Limites** : exécutions de suites séparées. Pas de nouvelle régression globale de tous les tests sur le même commit. Aucun contrôle des interventions LIVE, des approbations réelles, ni des modèles DGX en temps réel.

## 2. Gel opérationnel jusqu'à la présentation

- Aucun `docker compose up --build`, redémarrage, migration SQL ou déploiement de Policy/Worker.
- Ne jamais désactiver le veto LIVE ni modifier `AIOPS_POLICY_EMERGENCY_STOP` pour une démonstration.
- Vérifier l'état sans écriture : `python3 tools/acme_demo_ui_preflight_v2111.py` et `/tmp/aiops-browser-qa/bin/python tools/acme_browser_preflight_v2113.py`.
- La simulation Paie du portail ne modifie pas le registre Policy réel.
- Pour le DGX, utiliser le run historique `RUN-A4449145A6E377FF`. Le run enrichi `RUN-56C124FC8F7A0490` s'est arrêté sur `INTELLIGENCE_UNAVAILABLE`, pas sur une objection Critic.

## 3. Plan de reprise architecturale (post-demo)

### P0 — Contrôle réellement opposable
1. Cartographier précisément **toutes** les voies d'effet (Worker, Temporal, scripts, n8n, intégrations, exécuteurs externes).
2. Placer une décision Policy vérifiable juste avant chaque effet ; inventorier et refuser toute voie de contournement.
3. Utiliser identité de service mTLS/OIDC et une approbation humaine signée/horodatée (jamais un simple champ booléen fourni par l'IA).
4. Journal append-only, idempotence et clé d'opération ; recouper les changements de révision avec la mise en route effective.
5. Traiter les opérations déjà en cours (annulation coopérative, compensation / rollback testés) ; `STOP_AUTO` ne les interrompt pas aujourd'hui.
6. Qualifier les basculements multiserveurs : SQLite local ne suffit pas à garantir une politique globale atomique sans coordination.

Critère de sortie : démonstration sur environnement isolé qu'aucun effet réel ne peut être produit après retrait d'autorisation ou panne du Policy Store, y compris en concurrence et multi-instance. Ne pas déclarer LIVE qualifié avant cela.

### P1 — Fiabilité du raisonnement DGX
- Reproduire le `INTELLIGENCE_UNAVAILABLE` avec traces non sensibles ; distinguer transport, modèle, parsing, contexte et timeout.
- Mettre en place un fallback **explicite et traçable** vers diagnostic manuel et non vers remédiation automatique.
- Exiger des preuves liées à la télémétrie et à la CMDB ; ne pas présenter les exemples synthétiques comme des résultats DGX.

### P2 — HITL et expérience utilisateur
- Workflow approbation à 2 personnes indépendantes si nécessaire, expiration, révocation, contexte du changement et journal d'audit.
- Vue distincte des propositions, approbations, décisions Policy et exécutions, avec leurs statuts.
- Tests E2E navigateur et API séparant démonstration narrative des données d'exploitation.

## 4. Conditions pour toute nouvelle release

- PR dédiée, revue, tests unitaires et d'intégration, scans de dépendances, preuve de non-régression.
- Revue de menace avant le raccordement de la moindre action réelle.
- Déploiement de staging identifié puis rollback qualifié avant production.
- Publication d'un manifeste : commit, version, horodatages UTC, périmètre, SHA-256 des artefacts et résultats réels des tests.
- Les résultats attendus ne sont pas des tests exécutés. Toute validation incomplète reste signalée.
