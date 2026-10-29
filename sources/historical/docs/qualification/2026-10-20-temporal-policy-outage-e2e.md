# AIOps 2.0 — Rapport de qualification E2E Temporal, Intelligence et panne Policy

**Date :** 20 octobre 2026 (CEST)  
**Statut :** DEMO isolée — sécurité fail-closed vérifiée; **promotion opérationnelle interdite**  
**Origine des preuves :** sorties Docker, API Core/Evidence/Intelligence, historiques Temporal, SQL PostgreSQL et journal systemd communiqués pendant la recette sur `SRV-DEB-05`. Les traces sont transcrites ici, **pas collectées ni relancées par GitHub CI**.  
**Référentiel :** `alimtalbi-ata/aiops`. Worker candidat `b870f484fa009441fe37050b733cf729ff2e2f4b`; Intelligence candidate `cf09ec31a4cd82286bbf0117c9af3b352d2802ad`. Images OCI locales portant ces révisions (étiquettes déclaratives, non attestations signées).

## 1. Périmètre et barrières

Laboratoire Docker rootless `aiops2-e2e-v1` sous `/home/aiops/aiops2-e2e-lab`, réseaux dédiés `control`, `data`, `temporal_data` internes, **aucun port hôte publié** pour les services qualifiés. PostgreSQL applicatif et PostgreSQL Temporal séparés; namespace Temporal `default`, task queue `aiops-runner`. Services Core, Evidence, Policy, Twin, Intelligence, Worker, fournisseur LLM déterministe et Temporal. Aucun DGX externe, aucune remédiation LIVE, aucune modification de la stack opérationnelle `aiops2-rebuild` (dont Policy est resté healthy).

Le fournisseur `app/test_provider/main.py` est un **simulateur de règles déterministes OpenAI-compatible**, pas un véritable modèle IA ni une mesure de qualité diagnostique. Le mode `DEMO` peut simuler des étapes; la non-exécution des étapes après Critic est vérifiée via les événements Core.

## 2. Préqualification des composants

| Cas | Résultat observé |
|---|---|
| Base applicative, migrations et FK | PASS, après correction de permissions dans la copie laboratoire |
| Evidence : refus sans authentification; déduplication; conflit external_id | PASS (HTTP 401, déduplication, HTTP 409) |
| Twin construit depuis sources isolées, HTTP /health | `E2E_TWIN_READY=PASS` |
| Fournisseur déterministe : premier build | FAIL : `/app/main.py Permission denied` (`600` et user `10001:10001`) |
| Permissions de la copie source corrigées; reconstruction ciblée | `TEST_LLM_PACKAGING_FIXED=PASS`, /health 200 |
| Intelligence `cf09ec3` | `INTELLIGENCE_CANDIDATE_READY=PASS`, /health 200 |
| Analyst avec preuve SAN fraîche | Contrat 2.0 PASS, sévérité P1 |
| Critic avec preuve fraîche cohérente | `validated=true`, `ESCALATE` (comportement normal; ancienne assertion attendant false incorrecte) |
| Critic avec deux instantanés SAN contradictoires (1/4 et 3/4) | `INTELLIGENCE_FAIL_CLOSED_FIXTURE=PASS`, `validated=false`, issue `CONTRADICTION`, `HUMAN_APPROVAL`, `execution_allowed=false` |
| Worker `b870f48`, poller Temporal HTTP /health | `E2E_WORKER_TEMPORAL_READY=PASS` |

Une assertion erronée de préparation exigeait zéro événement sur run créé; Core crée normalement `INGEST/RUN_CREATED`, version 1. Le run a été récupéré sans suppression ni recréation.

## 3. Deux campagnes Golden Payment déterministes, Policy disponible

| Mesure | Campagne A | Campagne B |
|---|---|---|
| Core run_id | `RUN-D885843CC98AAC53` | `RUN-46E80E7EFB278E93` |
| Evidence synthétiques contradictoires | Oui | Oui |
| Temporal workflow status | `COMPLETED` | `COMPLETED` |
| Temporal workflow result | `BLOCKED` | `BLOCKED` |
| Temporal final_version | 17 | 17 |
| Temporal HistoryLength | 53 | 53 |
| Analyst / Critic / Policy ledger counts | 1 / 1 / 1 | 1 / 1 / 1 |
| Critic validated | false | false |
| Policy state / decision | BLOCKED / HUMAN_APPROVAL ou ESCALATE (assertion vérifiée) | BLOCKED / HUMAN_APPROVAL ou ESCALATE (assertion vérifiée) |
| HITL / REMEDIATE / étapes post-Critic | Aucune démarrée | Aucune démarrée |
| SQL jointures et absence d'événements tardifs | `FAIL_CLOSED_AUDIT=PASS` | `FAIL_CLOSED_AUDIT=PASS` |

Étapes démarrées : `NORMALIZE`, `CORRELATE`, `CMDB`, `OBSERVE`, `RAG`, `DGX_ANALYST`, `DGX_CRITIC`. Policy a été évaluée via le chemin de refus terminal du Worker, et non comme étape normale démarrée du workflow.

**Interprétation :** `Temporal COMPLETED` signifie succès technique du workflow; le résultat métier `BLOCKED` interdit la suite. Les deux vérifications sont distinctes.

## 4. Campagne de résilience — Policy indisponible

**Run :** `RUN-900218229559A6A3`  
**Scénario :** `GOLDEN-POLICY-OUTAGE-b23ffbf74ceb`  
**État initial :** `CREATED`, version 1, événement `INGEST/RUN_CREATED` uniquement, deux preuves SAN contradictoires; aucune exécution antérieure.

**Méthode :** unité utilisateur systemd `aiops2-e2e-policy-outage-campaign-v1.service`, exécution indépendante de SSH; arrêt ciblé du seul conteneur Policy de projet `aiops2-e2e-v1`; timer de secours `aiops2-e2e-policy-campaign-rescue-v1.timer` plus restauration `trap`; rétablissement rapide du service après scénario. Production hors périmètre.

Chronologie extraite du journal systemd du 20/10/2026 :

- **17:33:05** `INITIAL_STATE=PASS`; `RESCUE_ARMED=PASS`
- **17:33:06** `POLICY_LAB_STOPPED=PASS`, `POLICY_UNAVAILABLE=PASS`, `WORKFLOW_STARTED=PASS`
- **17:33:08** `RUN_STATUS=BLOCKED`; Analyst=1, Critic=1, Policy=0; `NO_POST_CRITIC_EFFECTS=PASS`
- **17:33:09** `POLICY_RESTORE_COMMAND=PASS`
- **17:33:11** `POLICY_RESTORED_HTTP=PASS`, `POLICY_OUTAGE_CAMPAIGN=PASS`
- Après campagne : `systemd Result=success`, `ExecMainStatus=0`, `ActiveState=inactive`.

Historique Temporal :
```text
WorkflowId RUN-900218229559A6A3
Namespace default
TaskQueue aiops-runner
HistoryLength 53
Status COMPLETED
Result {"final_version":17,"run_id":"RUN-900218229559A6A3","status":"BLOCKED"}
```

Journal Worker :
```text
critic_denial_persistence_failed: ConnectionError
```

**Verdict sécurité : PASS.** Le run est `BLOCKED` en présence du refus Critic, sans démarrage HITL, REMEDIATE, VERIFY, RECONCILE ou LEARN; récupération Policy et HTTP `/health` PASS.  
**Verdict audit : FAIL / écart P0.** Une décision Policy n'a pas été enregistrée (0 ligne dans AI Ledger) pendant l'indisponibilité. La restauration n'a pas déclenché de réconciliation démontrée. Une erreur logguée ne constitue pas une piste d'audit transactionnelle durable suffisante.

Après la campagne, le nettoyage utilisateur a donné :
```text
0 timers listed.
POLICY=running
POLICY_OUTAGE_CLEANUP=COMPLETE
```

## 5. Écarts connus / exigences avant promotion

1. **P0 — journal durable de refus** indépendant de la disponibilité Policy, adossé à une transaction et avec clé idempotente stable (`run_id`, `critique_id`, type de décision), statut `PENDING` puis `RECONCILED`, avec provenance/horodatage. L'arrêt de l'exécution doit rester indépendant d'une écriture réseau Policy.
2. **P0 — réconciliation** après restauration Policy, rejet de doublons et contradictions, backoff borné, statut de réconciliation observable. Ne jamais créer rétroactivement une autorisation.
3. **P0 — injection de panne et redémarrage** : Policy indisponible, Core indisponible, DB indisponible, redémarrage Worker entre rejet et blocage, retries Temporal, concurrence et rejeu.
4. **P1 — packaging reproductible** : Dockerfile du fournisseur déterministe avec permissions explicites compatibles avec utilisateur non privilégié; éviter la dépendance aux modes des sources extraites.
5. **P1 — observabilité / preuves** : suites automatisées publiant tests + historiques Temporal + requêtes SQL + statuts systemd, après suppression de tout secret et donnée sensible.
6. **Non testé** : modèle DGX réel, haute disponibilité, charge, véritable remédiation, garanties LIVE, attestation cryptographique des images.

## 6. Gate de promotion

**NO-GO production à la date de ce rapport.** Autoriser uniquement le périmètre DEMO isolé. Une nouvelle candidate Worker devra démontrer `BLOCKED` même si Policy ou son audit échoue, puis démontrer la récupération durable du refus avec exact-once logique et références d'audit stables. Les tests doivent être repris avec preuves nouvelles et versions immuables.

Ce rapport documente les sorties effectivement observées et les limites. Aucun test n'a été exécuté par cette modification GitHub et les essais locaux de l'utilisateur ne sont pas présentés comme CI GitHub.
