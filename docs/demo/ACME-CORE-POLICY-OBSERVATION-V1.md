# ACME DEMO — lecture Core/Policy persistée v1

## Périmètre

`GET /api/noc/runs/{run_id}/policy-status` est une **lecture interne**, authentifiée par le même Bearer de service que `GET /api/noc/runs/{run_id}`. Elle lit une seule projection SQL de `aiops.runs`, `aiops.incidents` et de l'éventuelle ligne `aiops.gates` pour `stage='POLICY'`. Aucune commande Core, Policy, Temporal, HITL ou LIVE n'est appelée. L'accès navigateur/viewer et l'ACL tenant runtime **ne sont pas qualifiés** : ne pas exposer directement cette route au portail public.

Schéma de réponse : `aiops.core-demo-policy-observation.v1`, provenance `CORE_POSTGRES_SYNTHETIC_READ`. Champs d'identité : `run_id`, `incident_id`, `mode=DEMO`, `run_status`. Champs Policy : `policy_gate_state` (`PASS`, `UNKNOWN`, `BLOCKED` ou `MISSING`), `policy_decision` (`SIMULATE`, `HUMAN_APPROVAL`, `ESCALATE` ou `null`), `policy_gate_recorded`, `explanation_code`. Tous les indicateurs `runtime_attested`, `policy_http_verified`, `hitl_approval_verified`, `temporal_execution_verified`, `postchecks_verified`, `rollback_verified`, `tenant_acl_qualified` et `live_remediation_authorized` valent **false**. Aucun texte `reason`, payload incident, secret ou URL d'infrastructure n'est retourné.

## Interprétation stricte des états

| État Core / gate persistée | `explanation_code` | Ce que cela démontre |
| --- | --- | --- |
| `BLOCKED` / absente | `BLOCKED_WITHOUT_POLICY_GATE` | Run bloqué et aucune gate Policy enregistrée ; **pas** de causalité établie |
| `BLOCKED` / `UNKNOWN+HUMAN_APPROVAL` | `BLOCKED_CAUSE_NOT_ESTABLISHED` | Gate conservée, sans preuve que celle-ci a provoqué le blocage |
| `RESOLVED` / `PASS+SIMULATE` | `RESOLVED_WITH_SIMULATE_GATE_NOT_LIVE` | État Core résolu et disposition SIMULATE persistée ; **aucune remédiation LIVE** |
| `RESOLVED` / absente ou non PASS | `RESOLVED_POLICY_SIMULATION_UNVERIFIED` | Résolution Core sans preuve de gate de simulation |
| `RUNNING` / quelconque | `RUNNING_NO_TERMINAL_PROOF` | Aucune conclusion sur durée, cause ou terminaison Temporal |
| Autres états | `RUN_STATE_NOT_REMEDIATION_PROOF` | Aucun effet réel attesté |

Une gate dont `evaluated_at` précède `runs.created_at` ou dépasse `statement_timestamp()` de lecture, ou un Run créé dans le futur, est rejeté. Cette chronologie est comparée avec l'horloge PostgreSQL et ne constitue ni une signature ni une preuve d'exécution. Une gate `PASS+ALLOW` sur DEMO, ou une combinaison incohérente, déclenche HTTP 503 `demo_policy_observation_unavailable`, sans divulgation des champs. Identifiant invalide, incident non synthétique, mode LIVE, absence d'incident, payload de tenant ambigu ou auth manquante : refus 401/503 avec `Cache-Control: no-store`.

## Contrat de coordination Explore / Story

Les observations rapportées le 28/10/2026 (7 runs DEMO : 5 BLOCKED, 1 RESOLVED, 1 RUNNING ancien) **ne sont pas interrogées par ce code en production**. Les tests CI créent leurs propres Runs synthétiques, sans réutiliser ces identifiants. Pour afficher ces états dans Story, le lot portail doit d'abord qualifier un accès viewer→Core sous ACL tenant, lier explicitement les `run_id`/`incident_id` du scénario et éviter de remplacer les IDs `SIM-...` des fixtures par des IDs réels sans liaison vérifiée. Une absence de gate est `MISSING`, pas une décision de refus Policy prouvée. Un RUNNING ancien n'est pas déclaré « bloqué » ou « timeout » sans observation temporelle authentifiée.

Le lot HITL/Temporal pourra consommer cette projection comme **observation**, jamais comme autorisation. Le reçu HITL expirant, le workflow Temporal, les postchecks et le rollback restent à raccorder et tester sur de vrais services CI. Ne pas assimiler la décision Policy `SIMULATE` à une exécution ou une restauration.

## Durcissement du parseur de sonde locale

Le consommateur CLI `scripts/probe_demo_policy_readonly.py` refuse les clés JSON dupliquées, y compris imbriquées, et les constantes non JSON `NaN`/`Infinity`/`-Infinity`. Ces valeurs ambiguës sont **BLOCKED**, jamais interprétées comme une disposition Policy. La lecture Core reste sur loopback, sous Bearer interne, sans redirection ni proxy. Ce contrôle ne qualifie ni HITL/Temporal, ni RBAC tenant, ni une exécution LIVE. Le contrat de sortie `aiops.demo-policy-readonly-probe.v1` ne change pas ; le parseur est seulement plus strict.

Qualification : `tests/test_core_demo_policy_real_integration.py` via le job existant `core-postgres-noc-real-integration` de `.github/workflows/quality.yml`. PostgreSQL 16 et Core HTTP sont de vrais services CI éphémères, mais Policy HTTP, Temporal, HITL et l'ACL tenant ne sont pas intégrés dans cette suite.

## Sonde locale : encodage et en-têtes HTTP canoniques (P0)

Le consommateur en lecture seule exige maintenant un corps JSON **UTF-8 sans BOM**, et refuse UTF-16/UTF-32, les en-têtes `Cache-Control` ou `Content-Type` dupliqués, tout `Content-Encoding` autre que l'identité, et un `charset` autre que UTF-8. La réponse Core HTTP normale reste admise ; une ambiguïté est `BLOCKED`, jamais convertie en preuve Policy ou LIVE. Contrats API et CLI v1 inchangés, durcissement du transport uniquement. Les rejets sont des tests de parseur/en-têtes (fixtures locales), tandis que le cas positif provient de Core HTTP + PostgreSQL éphémères dans `quality.yml`. Aucune qualification HITL/Temporal/Evidence ni Debian n'en découle.
