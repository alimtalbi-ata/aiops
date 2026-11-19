# TEAM C — SAN P1 → Payments : parcours intelligent explicable

**État au 2026-11-19 :** contrat et scénario **PROPOSED** ; intégration RUNTIME_SANDBOX **NOT_TESTED / BLOCKED**. Ce document ne transforme pas les reçus fixture ou CI offline en attestation runtime.

## 1. Périmètre et réutilisation

- **#818 (INT-07 / ABC)** : réutiliser les projections Twin, provenance, Analyst/Critic et collecteur offline. La revue Analyst/Critic actuellement lue annonce explicitement `DETERMINISTIC_RULES_NOT_LLM`, `HYPOTHESIS_ONLY`, `HOLD_FOR_HUMAN_REVIEW` et `DENY_LIVE_ACTION` : c'est une trace explicable synthétique, pas une invocation LLM ni une autorisation.
- **#813 / #805** : réutiliser le modèle Pydantic strict, le reçu V1, les 17 stages, les fixtures versionnées et le garde-fou Worker no-effect. Le reçu V1 est structurel ; il n'atteste pas à lui seul le SHA exécuté ni les liens cryptographiques inter-étapes.
- **Worker / Temporal** : réutiliser `IncidentWorkflow` et l'activité simulée existante uniquement dans la pile isolée autorisée. L'enregistrement no-effect est opt-in ; dans l'état lu, il refuse les autorités sandbox non attestées. Ne pas exposer de readbacks fournis par l'appelant comme autorité.
- **Policy / HITL** : décision par défaut fail-closed. HITL est une approbation simulée émise par `TWIN_ACME_SIMULATED`, jamais une approbation humaine réelle.

Aucun second orchestrateur, aucun endpoint live nouveau, aucun appel Core/GLPI réel, aucun ticket métier réel.

## 2. Contrat de liaison

Le JSON Schema compagnon définit une enveloppe additive autour du reçu V1. Il lie :
1. Run : `run_id`, `incident_id`, `attempt_id`, tenant, scénario, clé idempotente ;
2. code exécuté : `executed_sha` comparé par le vérificateur à un `expected_sha` de confiance ;
3. intelligence : hypothèses Analyst, objections Critic, références Evidence et limites d'autorité ;
4. Policy/HITL : raison, décision, identité d'approbation simulée, interdiction des effets ;
5. Worker : workflow Temporal, task queue isolée, activité no-effect ;
6. reçu V1 : digest SHA-256 et set exact des 17 étapes ;
7. attestations par étape : issuer, digest, UTC, run_id et attempt_id identiques ;
8. provenance : source fixture ou readback sandbox authentifié, sans mélange de namespaces.

**Règles d'identité :**
- `STORY_OFFLINE` : `run_id=SIM-ACME-*`, `tenant_id=null`, `attempt_id=ACME-SIM-[A-F0-9]{16}`. Ces identités restent non liées et ne sont jamais promues en `ACME-TEST`.
- `RUNTIME_SANDBOX` : tenant exact `ACME-TEST`, scénario exact `ACME-SAN-PAYMENTS`, ticket `SIM-GLPI-*`, approbation `SIM-APP-*`. Les identifiants doivent être relus depuis les autorités indépendantes ; ne pas les inventer ni les déduire d'une fixture.
- L'idempotency key est l'`attempt_id` pour rester aligné sur le contrat Worker existant. Même clé + même intention = replay sans nouvel effet ; même clé + intention différente = rejet.
- Tous les timestamps sont UTC explicites avec suffixe `Z`. Horodatage futur, périmé, sans timezone ou désaccord entre étapes = BLOCK.

Le schéma n'est pas un validateur runtime : la comparaison de `executed_sha == expected_sha`, le calcul des digests sur octets canoniques, les jointures d'identité et la preuve d'origine doivent être exécutés par le vérificateur autorisé. Tant que ce vérificateur n'existe pas, résultat = NOT_ATTESTED.

## 3. Séquence de démonstration

| Étape | Acteur | Entrée / sortie attendue | Garde |
|---|---|---|---|
| 01 | NOC / Simulator | incident SAN P1 synthétique, tenant et signaux | source fixture étiquetée |
| 02 | Twin | chemin SAN → stockage → service Payments | graphe structurel, causalité UNKNOWN |
| 03 | Evidence | références, SHA-256 source, UTC/fraîcheur | pas de provenance implicite |
| 04 | Analyst | hypothèses, confiance, vérifications demandées | HYPOTHESIS_ONLY |
| 05 | Critic | objections indépendantes et preuves manquantes | HOLD_FOR_HUMAN_REVIEW |
| 06 | Policy | DENY_LIVE_ACTION ou SIMULATE | aucun bypass |
| 07 | HITL | décision TWIN_ACME_SIMULATED | human_approval_claimed=false |
| 08 | Worker / Temporal | workflow isolé, attempt_id, no-effect receipt | aucun effet métier |
| 09 | Core / Evidence | Run et Evidence reliés par IDs exacts | aucune jointure par nom seul |
| 10 | Reçu | 17 stages + digests + SHA + UTC | vérification fail-closed |
| 11 | Workbench | Run, Evidence, simulation et limites dans une chronologie | un Run canonique |
| 12 | Verdict | GO_SIMULATION_ONLY seulement si toutes preuves qualifiées | LIVE = NO_GO |

Le reçu V1 impose les 17 étapes suivantes : `capability_simulator`, `capability_core`, `capability_twin`, `capability_policy`, `capability_worker`, `simulator_start`, `pre_resolution_core`, `pre_resolution_twin`, `pre_resolution_policy`, `pre_resolution_worker`, `worker_no_effect`, `core_finalization`, `post_resolution_core`, `post_resolution_twin`, `post_resolution_policy`, `post_resolution_worker`, `resolved`. Une étape absente, dupliquée, non PASS ou rattachée à un autre Run/attempt rejette le reçu.

## 4. Tests d'acceptation

**Positifs**
- fixture STORY_OFFLINE valide, 17 étapes PASS, IDs et SHA conformes ;
- hypothèse Analyst accompagnée d'au moins une référence Evidence ;
- objection Critic conservée, indépendance runtime explicitement false ;
- décision Policy DENY_LIVE_ACTION, HITL simulé, Worker no-effect ;
- UTC cohérent, digest 64 hex, SHA exécuté 40 hex et même identité sur les 17 attestations ;
- replay idempotent de même attempt sans nouvel effet.

**Négatifs / fail-closed**
- tentative de tenant ACME-TEST dans STORY_OFFLINE ou promotion SIM-ACME vers Core ;
- ticket non SIM-GLPI, approval non SIM-APP, issuer HITL non simulé ;
- LIVE, human_approval_claimed=true, execution_allowed=true, effect_allowed=true ;
- Critic absent, objections vides, preuve non référencée ou provenance fixture présentée comme runtime ;
- SHA exécuté différent de expected_sha, digest altéré, étape dupliquée/manquante ou identité inter-étapes divergente ;
- timestamp non UTC, futur, stale, ou horloges contradictoires ;
- clé idempotente réutilisée avec payload différent ;
- capability Core/Twin/Policy/Worker absente, readback non authentifié, Temporal history non vérifiable ;
- tout effet Docker, Core write non autorisé, GLPI réel ou action métier LIVE.

## 5. Démonstration contrôlée et verdict

Le parcours immédiatement démontrable est **STORY_OFFLINE** : il présente hypothèses, objections, preuves synthétiques, décision Policy/HITL et les 17 étapes comme scénario contractuel. Il doit afficher visiblement `LOCAL_SYNTHETIC_FIXTURE`, `runtime_attested=false`, fraîcheur UNKNOWN et `LIVE=NO_GO`.

Le parcours **RUNTIME_SANDBOX** reste BLOCKED tant que les cinq capacités, l'identité du SHA exécuté, les readbacks authentifiés indépendants, la liaison Temporal/Core/Twin et le reçu runtime exact ne sont pas produits dans la pile jetable. Le collecteur offline ne constitue pas cette preuve. Aucun déploiement Debian n'est demandé ici.

## 6. Limites, dépendances et sortie

- Dépendances : #818 (base candidate ABC), #813 (orchestration/reçu), #805 (modèle strict), #802 (gate 17 stages).
- Aucun statut CI exact-SHA n'a été observé dans les status contexts au moment de préparation ; tests locaux/runtimes non exécutés dans cette session.
- Le SHA du code exécuté doit être celui de la pile sandbox, non le SHA de cette PR documentaire.
- La présente PR ajoute contrat, scénario et tests statiques uniquement ; elle ne modifie pas l'orchestrateur, Worker, Policy, Temporal, Debian ou GLPI.
- Draft only ; revue CENTRAL requise avant toute promotion. Aucun merge sans CENTRAL.
