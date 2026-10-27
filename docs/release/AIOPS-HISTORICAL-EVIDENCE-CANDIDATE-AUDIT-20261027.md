# AIOps — Audit initial des candidats historiques Evidence / Read Model

**Date :** 27 octobre 2026  
**Branche auditée :** `feat/v21310-star-portal-continuity-20261022`  
**Conclusion :** les noms V145 de l'inventaire sont des pistes, mais leur code source n'a pas été retrouvé dans les arbres GitHub vérifiés. En revanche, le dépôt actuel contient des équivalents partiels pour l'identité, la validation et l'ingestion de preuves, ainsi qu'un read model ACME explicitement synthétique. Aucun candidat historique n'est déclaré réutilisable sans récupération de son source exact.

## 1. Périmètre et limites

- Inspection des arbres Git de la branche de travail et des branches historiques visibles `feat/demo-visual-evidence-center-20261026`, `feat/v21329-star-proof-readiness-20261023` et `feature/r33-schema-reconciliation-2026-10-19`.
- Recherche des chemins `v145-d4.57-evidence-acquisition`, `v145-d4.55-evidence-fusion`, `v145-d4.56-evidence-matrix`, `functional-read-model`, `decision-adapter` et variantes associées : **aucun résultat dans le code indexé de la branche courante**. Les arbres examinés des branches de démonstration/proof ne contiennent pas ces chemins non plus.
- Ce constat ne permet pas de conclure que le code n'existe pas dans le serveur Debian, une archive ZIP, une autre branche non visible ou un export de conversation. Il signifie uniquement que le code exact n'est pas récupérable par ces chemins GitHub inspectés.
- Aucun accès au serveur Debian, aucune exécution de tests dans un clone local, aucune connexion à une base, aucun changement runtime.

## 2. Sources actuelles vérifiées dans GitHub

| Fichier / référence | Ce qui est réellement présent dans la source | Réutilisation possible | Limite importante |
|---|---|---|---|
| `app/shared/evidence_identity.py` — blob `ae36976d3c6db18e8d64c4434fbc2199d4b16bc4` | Canonicalisation de l'enveloppe, normalisation ISO8601 avec fuseau, SHA-256 déterministe | Base actuelle pour l'identité et le rejeu des preuves | La fonction calcule une empreinte d'enveloppe ; elle ne prouve pas que la source amont est authentique |
| `app/shared/evidence_contract.py` — blob `4b22ef4afca633b7162a78fbdb3eadf808a2997d` | Contrôles d'IDs dupliqués, timestamps contradictoires, hash, fraîcheur, preuves de sévérité, contradictions de snapshots et références Critic | Équivalent partiel d'une Evidence Matrix/fusion diagnostique | Pas un moteur générique complet de fusion multi-connecteurs ; les appels doivent être intégrés au flux réellement utilisé |
| `app/evidence/main.py` — blob `517efa3e4872b384cf354c83ad62f52ed7975538` | API GET/POST, authentification interne, insertion append-only, déduplication idempotente, conflit 409 si ID externe réutilisé avec données différentes | Point de départ actuel pour l'acquisition et la persistance | Les tests lus sont des tests API avec DB simulée ; ils ne prouvent ni connexion à des sources réelles ni comportement PostgreSQL runtime |
| `tests/test_evidence_ingestion.py` — blob `b6da4dccffe1cc59376922bb72b958d1f896de5c` | Cas d'insertion, replay, conflit, timestamp sans fuseau, identité réservée et refus d'auth | Contrat de test de base pour toute reprise/adaptation | La DB est mockée ; ajouter intégration PostgreSQL isolée et tests de concurrence avant qualification |
| `app/portal/acme_impact_read_model.py` — blob `3d9d2900b2507f9e14dafd71504e6921fbc44c76` | Read model à partir d'un fichier fixture local, lecture bornée, anti-symlink, hash du contenu et labels SIMULATED | Référence pour la sécurité d'un read model statique et sa provenance | Ne contacte aucun backend ; run/ticket/horodatage runtime sont volontairement absents |
| `tests/test_portal_acme_impact_read_model.py` — blob `635181af79083f2f910ff7eb6479f99dd9bed3a9` | Vérifie routes GET, déterminisme, empreinte, SVG, échappement HTML et provenance synthétique | Tests de non-régression du mode démo | Ne constitue pas une qualification de connectivité GLPI, NOC, SAN ou Payments |
| `tools/schema_reconcile.py` sur branche historique `feature/r33-schema-reconciliation-2026-10-19` — blob `e788ff0f5fb4d2487768888263f363521d969099` | Compare uniquement des noms de tables legacy/V1/V2 à partir de fichiers texte ; génère JSON/Markdown ; retourne explicitement `COMPATIBILITY_VERIFIED=NO` | Réutilisable pour pré-tri offline d'inventaires | Comparaison de noms uniquement ; aucune inspection de colonnes, contraintes, données ou comportement. Ne pas l'utiliser comme feu vert de migration |
| `tests/test_schema_reconcile.py` sur la même branche — blob `483120cea2f473917e707324d59fe669d913b812` | Trois tests de parsing/classification et rappel que le recouvrement de noms n'est pas une compatibilité | Tests à conserver si l'outil est repris | Ne valide pas un schéma ou une migration réelle |

## 3. Décision de réutilisation initiale

| Candidat | Décision actuelle | Motif |
|---|---|---|
| V145 Evidence Acquisition | **UNKNOWN — récupérer le source** | Chemin/source exact non retrouvé ; pas de comparaison possible |
| V145 Evidence Fusion | **NE PAS importer pour l'instant** | `evidence_contract.py` possède déjà des gardes diagnostiques partielles ; éviter une deuxième logique avant de comparer les contrats |
| V145 Evidence Matrix | **ADAPTER/ÉVALUER l'existant d'abord** | Le contrôle de qualité existe partiellement, mais une vraie matrice UI/read model multi-source reste à prouver |
| V145 Functional Read Model | **UNKNOWN — récupérer le source** | Aucun code candidat retrouvé ; l'ACME read model actuel est une fixture et non un agrégateur live |
| V145 Decision Adapter | **UNKNOWN — récupérer le source** | Aucun code candidat retrouvé ; comparer d'abord les contrats canoniques actuels |
| R33 schema reconcile | **RÉUTILISATION CONDITIONNELLE pour inventaire offline** | Code source et tests retrouvés ; méthode explicitement limitée aux noms de tables |
| ACME impact read model actuel | **CONSERVER pour DEMO/SIM uniquement** | Contrat de provenance clair ; ne pas le requalifier comme intégration live |
| Evidence service actuel | **CONSERVER comme base actuelle, qualification manquante** | Contrats de déduplication/append-only présents ; manque l'intégration réelle aux collecteurs et test DB isolé |

## 4. Écarts techniques prioritaires

1. **Collecteurs réels absents de cette preuve de code** : inventaire précis des sources SAN, stockage, Linux/ESXi, Prometheus, Checkmk/Thruk et GLPI, avec adaptateurs authentifiés en lecture seule, timeouts et provenance.
2. **Matrice explicative manquante ou non prouvée** : modèle par hypothèse/source avec statut soutenu/contredit/inconnu, âge, poids de source, identifiants et liens vers la décision.
3. **Séparation synthétique/réel** : maintenir `SIMULATED_TARGET` distinct de `LIVE`, exiger source identity + observed_at + external_id quand disponibles ; aucune fixture ne doit être promue comme preuve réelle.
4. **Qualification DB** : tests PostgreSQL jetable pour index unique, conflit d'identité, rejeu concurrent, transaction, append-only et rollback de transaction.
5. **Contrat read model** : champs source, availability, observed_at, fetched_at, freshness, status `FRESH/STALE/UNKNOWN`, reason codes et provenance ; échec partiel doit rester visible.
6. **Récupération historique** : retrouver le ZIP/chemin exact des modules V145 et calculer hashes avant de les ouvrir/exécuter. Ne pas lancer d'anciens scripts durant la phase d'inventaire.
7. **Sécurité de l'auth interne** : vérifier l'usage cohérent du jeton de service et la couverture des routes dans une qualification dédiée ; ce rapport ne déclare pas le service globalement sécurisé.

## 5. Prochaine unité de travail

- Ajouter un contrat versionné `evidence-source-adapter-v1` pour collecteurs en lecture seule, sans implémenter d'accès équipement LIVE dans cette tâche.
- Créer un modèle `evidence-matrix-read-model-v1` qui consomme les preuves normalisées et les résultats de garde existants, conserve les contradictions et explique les états inconnus.
- Ajouter tests unitaires pour source absente, horodatage périmé, contradiction, duplicate external ID, source non authentifiée, timeout et réponse partielle.
- Ajouter tests d'intégration PostgreSQL jetable si l'infrastructure de CI existante le permet.
- Une fois ces contrats couverts, reconsidérer la récupération de V145 pour éviter de dupliquer le travail.

## 6. Critère de preuve

Ce document est un audit de code source GitHub, pas une exécution de test. Les références de blob identifient le contenu consulté. Aucun PASS de CI, runtime ou production n'est affirmé ici.
