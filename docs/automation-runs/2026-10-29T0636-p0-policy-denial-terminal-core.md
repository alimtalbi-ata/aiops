# P0 Policy/HITL/Temporal — terminaliser un refus Policy DEMO dans Core (29/10/2026, 06:36 Paris)

## Contexte GitHub lu
- `main` : `27deb9b1a66faf27df8d69b137a63451f7649d80` ; `deploy/aiops2-stable` : `e54c4e9a9b37e6229559a1b587c9a06b4741a8b3` ; aucun changement de ces refs.
- PR existante #176, branche `fix/p0-policy-synthetic-critic-fence-20261029-0235`, SHA de départ `62034bb949f3147dc1498253e847dcd8db1acc8a`. Convergence historique #144/#147/#155/#163 via main, #173/#174 déjà intégrées.
- Travaux voisins consultés : #156 Recette, #153 déployeur, #170 Twin, #171 NOC, #169/#177 UI, #137 Story ; journaux `2026-10-29T0431-p0-temporal-synthetic-policy-disposition-fence.md` et `20261028-1030-hitl-policy-convergence.md`.
- Aucune PR additionnelle ni workflow CI ajouté. Aucun push stable, aucune opération Debian, aucune commande LIVE.

## Un seul correctif vertical P0
- Défaut : dans `execute_stage`, une réponse Policy `BLOCKED/HUMAN_APPROVAL` ou `UNKNOWN/HUMAN_APPROVAL` écrivait seulement l'événement `GATE_BLOCKED`. Core `add_event` met à jour l'état du *stage*, pas celui du *Run* ; le workflow retournait `BLOCKED` alors que le Run canonique pouvait rester `RUNNING`.
- Correction : après la gate persistée, le worker appelle la commande Core versionnée `BLOCK` avec clé idempotente `POLICY-DENIED-{run_id}`, **avant** l'événement `GATE_BLOCKED`. La réponse Core doit attester `run_id`, `status=BLOCKED` et `version` entier strict ; sinon échec fermé. L'événement utilise la nouvelle version.
- Prérequis Core corrigé : `set_stage` appelait `fetchone()` sur la connexion psycopg au lieu du curseur retourné par `execute()`, ce qui empêchait les événements de stage de se persister.
- Aucun changement du contrat public Policy ; contrat interne Worker→Core précisé : un refus de gate DEMO doit être suivi d'un Run canonique `BLOCKED` (version incrémentée), jamais d'un simple stage `BLOCKED`. Cette séquence n'est pas atomique ; en cas d'échec réseau après `BLOCK`, le Run reste bloqué mais l'événement peut manquer : **NO-GO**, diagnostic requis.

## Tests et limites
- Test AST dans `test_simulation_policy_contract.py` : exige la commande `BLOCK` avant l'événement et la version issue de Core. Test réel Core HTTP + Policy HTTP + PostgreSQL 16 éphémères dans `test_core_demo_policy_real_integration.py` : refus Critic et Evidence absente, gate, commande versionnée, événement, lecture de Run et rejeu idempotent. Ce test exerce directement les endpoints, **pas Temporal**.
- `quality.yml` existant inclut déjà les deux fichiers ; **CI PENDING sur le nouveau SHA**. Aucun test local/serveur prétendu exécuté. HITL authentifié, Temporal runtime, provenance Policy→Run/Evidence, isolation tenant A/B, impacts Payments, rollback et `applied.sha` Debian : **NOT_TESTED**.
- Les 7 Runs DEMO initiaux (5 BLOCKED sans gate, 1 RESOLVED/PASS/SIMULATE, 1 RUNNING ancien) restent des observations historiques non revérifiées. Ce correctif ne prouve pas leur cause et ne requalifie pas `RESOLVED` comme remédiation LIVE.

## Release et remise
- **NO-GO E2E / READY_FOR_STABLE=BLOCKED** tant que CI finale, assemblage, couverture déployeur Core/Worker/Policy/Twin/Portal, rollback et smoke-tests Debian attestés ne sont pas validés.
- Seule Recette 5/5 (#156) peut assembler et décider d'une promotion. Prochain lot : exécution Temporal sandbox sur Core/PostgreSQL/Policy éphémères, vérification du lien authentifié run_id/incident_id/evidence, puis recette post-déploiement en lecture seule et preuve `applied.sha`.

## CI intermédiaire rouge et correction du fixture
- SHA `55942df0c27f41a6b5f391088c6ac17d3cb3d901` : `quality.yml` [push #40824528371](https://github.com/alimtalbi-ata/aiops/actions/runs/40824528371) : `core-postgres-noc-real-integration` **FAILURE** sur les deux nouveaux cas ; `policy-and-static` et `grafana-real-integration` **SUCCESS**. Le job [PR #40824534411](https://github.com/alimtalbi-ata/aiops/actions/runs/40824534411) a également échoué sur Core.
- Cause vérifiée dans les logs PostgreSQL : `column "event_key" does not exist`. Le job éphémère ne chargeait que les migrations 001 et 004, alors que les commandes Core utilisent `event_key` introduit par 008.
- Correctif **dans le job existant** `core-postgres-noc-real-integration` de `quality.yml` : appliquer les migrations 006, 007 et 008 après 001/004. Aucune nouvelle CI, aucune migration appliquée sur Debian. Les tests du nouveau HEAD doivent être revérifiés ; ne pas masquer l'échec intermédiaire.
