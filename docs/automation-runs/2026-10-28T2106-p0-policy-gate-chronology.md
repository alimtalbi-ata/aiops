# 2026-10-28 21:06 Europe/Paris — P0 chronologie Policy DEMO

## Sources et SHA
- `main` HEAD avant modification : `b6cac31f6713d60f517bc6c4648002297fb87de6`.
- Base PR draft #144, SHA `7c849f40fa1878e2e98a968db11b4fc06f9b79c1` ; branche dédiée `fix/p0-core-policy-gate-chronology-20261028-2106` ; PR empilée sur #144.
- PR ouvertes et autres lots consultés : #143, #145 (Studio), #137 (HITL Story), #133 (scénario), #139 (NOC), #142 (Twin), #49→#106 (HITL). Journaux Explore/Story, E2E, continuité, migrations et `quality.yml` lus.
- État utilisateur des 7 Runs Debian (5 BLOCKED, 1 RESOLVED, 1 RUNNING) non revérifié. Aucune requête Debian, aucun impact Payments ni E2E prétendu.

## Code, tests et contrat
- `app/core/main.py` : jointure Policy existante étendue avec `runs.created_at`, `gates.evaluated_at` et `statement_timestamp()` dans la même lecture PostgreSQL.
- `app/shared/demo_policy_gate_read_model.py` : fail-closed pour Run futur, gate antérieure au Run, gate future, dates non timezone-aware ; aucune permission créée.
- `tests/test_core_demo_policy_real_integration.py` : 3 cas de rejet sur PostgreSQL 16 + Core HTTP réels éphémères ; conservation des cas BLOCKED/MISSING, RESOLVED/PASS+SIMULATE et RUNNING.
- `docs/demo/ACME-CORE-POLICY-OBSERVATION-V1.md` : contrat additif de validation ; schéma de réponse `aiops.core-demo-policy-observation.v1` inchangé. Aucun nouveau pipeline : `quality.yml` exécute déjà la suite dans `core-postgres-noc-real-integration`.
- Aucun schéma SQL, endpoint public, droit RBAC, jeton HITL ou effet LIVE modifié.

## Commit, PR et CI
- Commit code/tests/docs et PR : voir HEAD et métadonnées de la PR empilée.
- `quality.yml` sur HEAD final : **PENDING** jusqu'à vérification des jobs. Tests locaux **NOT_TESTED**.
- Core/PostgreSQL réels en CI : **PENDING**. Policy HTTP, HITL authentifié, Temporal, postchecks, rollback, ACL tenant runtime, sept Runs Debian, navigateur/captures/vidéo : **NOT_TESTED**.

## Risques et suite
- Dates persistées non signées ; un `RESOLVED` avec gate `PASS/SIMULATE` n'est pas une preuve LIVE. L'API exige le Bearer interne et ne doit pas être exposée au viewer sans ACL tenant.
- Prochain micro-lot : lier le Story au Run/incident canoniques avec ACL tenant qualifiée, puis tester le parcours HITL/Temporal sandbox sur services CI éphémères.
- Aucune fusion avant checks verts, absence de conflits et revue sécurité. Aucun accès/deploy Debian, aucune commande LIVE.

## Vérification CI GitHub du commit code/tests/docs initial

- PR draft [#147](https://github.com/alimtalbi-ata/aiops/pull/147), empilée sur #144 ; commit initial [`a987d6cc3d9f6fb1397fe2b1ab3d65bcf3a5a1dc`](https://github.com/alimtalbi-ata/aiops/commit/a987d6cc3d9f6fb1397fe2b1ab3d65bcf3a5a1dc).
- [quality pull_request #40760625283](https://github.com/alimtalbi-ata/aiops/actions/runs/40760625283) : `completed/success` sur ce SHA. Jobs `policy-and-static`, `core-postgres-noc-real-integration`, `grafana-real-integration` : **success**.
- [quality push #40760614741](https://github.com/alimtalbi-ata/aiops/actions/runs/40760614741) : `completed/success` sur ce même SHA.
- Étape `Real Core PostgreSQL DEMO Policy gate observation and refusals` : **success**, avec vraie instance PostgreSQL 16 et Core HTTP éphémères ; schéma SQL appliqué et Core prêt. Les cas négatifs de chronologie et les régressions sont inclus dans cette suite. Le statut du job ne vaut pas attestation des sept Runs Debian.
- `main` revérifié après CI : `b6cac31f6713d60f517bc6c4648002297fb87de6`. GitHub indique PR #147 `mergeable=true` ; **pas de fusion** : PR draft empilée sur #144, qualification tenant/Story encore manquante.
- Commentaires de coordination publiés sur #144 et #137 (contrat inchangé, route interne uniquement).
- La présente mise à jour du journal crée un **nouveau SHA documentaire** ; sa propre CI est à vérifier avant toute fusion. Aucune preuve HITL/Temporal/Payments/LIVE ajoutée.
