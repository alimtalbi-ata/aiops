# AIOps 2.0 — Architecture cible et avancement (2026-10-18)

## Produit
AIOps Core est un moteur autonome déployable chez des clients possédant déjà monitoring, ITSM, CMDB, IAM, applications, datacenters et infrastructures hétérogènes. Le Digital Twin ACME est un produit de laboratoire **facultatif** servant aux tests, qualifications, démonstrations et campagnes Chaos. Il ne fait pas partie des prérequis du Core.

## Architecture cible
INGEST → NORMALIZE → DEDUPLICATE → CORRELATE → CONTEXT/CMDB → EVIDENCE → RAG → DGX ANALYST → DGX CRITIC → POLICY/GATE → TEMPORAL → VERIFY → RECONCILE → AUDIT/LEARN. Portail, Copilot, HITL et connecteurs remplaçables. Fail-closed, idempotence, ownership/fencing, rollback.

## Déploiement courant
Un seul serveur Debian 10.79.94.202, utilisateur aiops, installation et volumes sous /home/aiops/. Docker Compose, sans Git sur Debian. Windows PowerShell : scp .\AIOps-2.0-V8-CLEAN-R3.zip aiops@10.79.94.202:/home/aiops/. Nommage stable aiops2_<fonction>, sans suffixe de version. Contrats internes : Core 810, Twin 811, Evidence 812, Policy 813, Copilot 814, Worker 815, Simulator 816, Intelligence 817, RAG 818, Integration 819, PostgreSQL 5432, Temporal 7233. Protéger ports 8096/8098/8099/8110 et R6 18111; vérifier avant publication des ports n8n 15678, GLPI 18080, Prometheus 19090, Grafana 13000, Temporal UI 18088.

## État réel
- R6 FIX3 : Core démonstrateur qualifié manuellement sur Debian 18111, sans Temporal, PostgreSQL ni DGX.
- CLEAN R2 : Core + schéma PostgreSQL et préflight, non qualifié sur Debian.
- CLEAN R3 : ajout manifeste de produit, inventaire Docker/TCP lecture seule, guide de transfert et état d'avancement; contrôles statiques locaux OK; démarrage Docker Debian NON testé.
- **Manquant** : Temporal réellement intégré, DGX Analyst/Critic, RAG, IAM/OIDC, connecteurs clients, GLPI, UI opérationnelle, Virtual Twin ACME.
- Aucun jeu de données ACME à injecter avant qualification du moteur Core.

## Sécurité et exploitation
Ne jamais effacer ou renommer automatiquement un conteneur, réseau ou volume existant. Inventaire lecture seule et résolution manuelle des conflits de noms avant déploiement. Aucun docker pull implicite; image manquante = échec explicite. Secrets générés à l'installation, non committés. Préserver main; développer via PR. La livraison reste le ZIP autonome SCP Windows → /home/aiops/.
