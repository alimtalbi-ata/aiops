# TEAM C — SAN P1 → Payments : Run Journey relié au cockpit existant

**État :** projection STORY_OFFLINE raccordée au cockpit ACME existant. Aucun Run Core ni attempt runtime n'est créé. Le reçu d'exécution est absent ; les 17 étapes restent NOT_RUN/MISSING.

## 1. Sources et réutilisation

- #818 / ACME fixture read model : source unique des octets fixture, digest SHA-256, Run simulé `SIM-ACME-*`, incident SAN P1 et incident Payments P2.
- Twin provenance / consumer : fournit le Run de scénario, les citations source_ref, le graphe structurel et le statut UNBOUND.
- Analyst/Critic existant : `DETERMINISTIC_RULES_NOT_LLM`, hypothèse uniquement, objection explicite, `HOLD_FOR_HUMAN_REVIEW`.
- Policy existante : `DENY_LIVE_ACTION`; aucune autorisation d'effet.
- Cockpit existant / #822 : la projection `run_journey` est intégrée au même objet de cockpit et affichée dans `/demo/acme-incident-cockpit`. Aucun portail, endpoint ou orchestrateur parallèle.
- HITL/Temporal : le cockpit ne les invoque pas. Il affiche `SIMULATED_NOT_REQUESTED` et `NOT_INVOKED`, sans inventer d'approval ID ni de workflow ID.

## 2. Identité et idempotence

- `run_id` est repris directement de `twin_evidence.run_id` et doit égaler `SIM-ACME-<16 premiers caractères du digest fixture en majuscules>`.
- `attempt_id` est une clé de corrélation synthétique dérivée du même digest : `ACME-SIM-<16 caractères>`. Elle n'est **pas** un Core attempt. `idempotency_key == attempt_id` dans le seul espace STORY_OFFLINE.
- `tenant_id=null`, `core_run_id=null`, `twin_evidence.attempt_id=null`, `binding_status=UNBOUND`. Aucun rattachement ACME-TEST ou production.
- `source_sha256` est l'empreinte des octets de la fixture ; ce n'est ni un Git SHA ni un SHA d'exécutable. `executed_sha=null`, `expected_sha=null`, `source_git_sha=null`.
- Aucun horodatage d'exécution n'est fabriqué : `collected_at=null`, `observed_at=null`. Les données de scénario horodatées ailleurs restent explicitement une horloge fixe de démo.

## 3. Run Journey v2 et 17 étapes

Le contrat `aiops.team-c.san-payments-run-journey.v2` est un adaptateur en lecture seule. Il reprend le Run Twin existant, les identifiants incident, le digest fixture, les hypothèses Analyst, objections Critic et raisons Policy. Les références Evidence pointent vers les citations de provenance déjà fournies par le consommateur Twin.

Les 17 étapes du reçu V1 sont exposées comme un **plan**, pas comme un reçu :
`capability_simulator`, `capability_core`, `capability_twin`, `capability_policy`, `capability_worker`, `simulator_start`, `pre_resolution_core`, `pre_resolution_twin`, `pre_resolution_policy`, `pre_resolution_worker`, `worker_no_effect`, `core_finalization`, `post_resolution_core`, `post_resolution_twin`, `post_resolution_policy`, `post_resolution_worker`, `resolved`.

Chaque étape est `status=NOT_RUN`, `evidence_state=MISSING`, `sha256=null`, `observed_at=null`. `receipt=null`. Aucune étape PASS, aucun reçu V1 et aucun ticket SIM-GLPI ne sont inventés.

## 4. Contrôles positifs et négatifs

**Positifs :**
- Run Journey utilise exactement le Run ID du Twin existant et du consumer Twin.
- Run / attempt / idempotency key stables et dérivés du même digest fixture.
- Incident ID égal à celui du cockpit ; digest identique sur impact, cockpit et provenance.
- 17 noms d'étape uniques et complets, toutes NOT_RUN/MISSING.
- L'UI affiche le même Run/attempt, l'absence de SHA exécuté, l'absence de tenant, de reçu et d'invocation Temporal.

**Négatifs :**
- refus de scope/tenant/runtime binding inattendu ;
- refus de digest fixture divergent ou Run ID Twin non correspondant ;
- refus d'Analyst/Critic/Policy non qualifié ou d'effet LIVE ;
- refus d'un reçu présent dans la projection STORY_OFFLINE ;
- refus de toute étape PASS, preuve MISSING transformée en attestée, identité Run/attempt divergente ;
- refus d'un approval HITL ou d'un workflow Temporal présenté comme exécuté.

## 5. Frontières de qualification

| Couche | État |
|---|---|
| Fixture / Twin / Analyst / Critic / Policy | STORY_OFFLINE, synthétique |
| Run ID | SIM-ACME, non Core |
| Attempt ID | corrélation synthétique, non Core |
| Evidence | citations de fixture, pas de preuve runtime |
| HITL | simulé non demandé, aucune approbation |
| Worker / Temporal | non invoqué |
| 17 étapes | plan NOT_RUN/MISSING |
| Reçu exécution | absent |
| RUNTIME_SANDBOX | BLOCKED / NOT_TESTED |
| LIVE / production | NO-GO |

## 6. Sécurité et livraison

- Aucun appel Core/GLPI réel, aucune écriture métier, aucun ticket réel.
- Aucun bypass Policy/HITL, aucune invocation Worker/Temporal.
- Aucun changement d'orchestrateur, aucun déploiement Debian, aucun cutover 7770.
- La PR reste Draft et attend la revue CENTRAL. Le PASS des tests offline ne qualifie ni runtime ni portail déployé.
