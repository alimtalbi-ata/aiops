# 2026-10-29 02:35 Europe/Paris — P0 Policy SIMULATE : refus des évaluations synthétiques non qualifiées

## Sources, base et coordination
- HEAD `main` observé avant la branche : `27deb9b1a66faf27df8d69b137a63451f7649d80` (fusion #174). Stable `deploy/aiops2-stable` observée : `e54c4e9a9b37e6229559a1b587c9a06b4741a8b3`, **inchangée**.
- Branch dédiée : `fix/p0-policy-synthetic-critic-fence-20261029-0235` ; [PR draft #176](https://github.com/alimtalbi-ata/aiops/pull/176) vers main, pas stable.
- PR historiques inspectées : #140 (ouverte), #141 (fusionnée), #142/#143/#145/#146 (ouvertes), #144/#147/#155 (fermées et portées dans main via #160), #163 (fusionnée), #173/#174 (fusionnées). Candidats concurrents : #169 UI, #170 Twin, #171 NOC, #175 poller et #156 Recette. Aucun merge massif, aucune duplication de leur périmètre.
- Journaux relus : `2026-10-29T0004-p0-policy-release-convergence.md`, `2026-10-29T0033-p0-policy-real-http-ci.md`, `2026-10-29T0144-p0-policy-core-unbound-crosscheck.md`. Contrat existant `app/shared/simulation_policy_contract.py` : le mapping DEMO/REPLAY/STORY→OBSERVE ne contourne **pas** les vérifications Evidence/Critic.

## Une micro-livraison verticale P0
- Défaut constaté dans le code `app/policy/main.py` : avec `evidence_count>0`, DEMO/REPLAY/STORY pouvait retourner `PASS/SIMULATE` même pour `critic_validated=false`, `redundancy_ok=false` ou `confidence<0.90`. Ce PASS affiché au client n'était pas justifié par les assertions reçues.
- Correction : `BLOCKED/HUMAN_APPROVAL` et raison fixe pour ces trois défauts. Les valeurs sûres `critic_validated=true`, `redundancy_ok=true`, `confidence>=0.90` continuent de donner `PASS/SIMULATE` en DEMO, sans effet réel. Le refus LIVE des commandes mutantes reste inchangé.
- Tests ciblés ajoutés aux suites **existantes** `tests/test_policy_safety.py` (unitaire) et `tests/test_policy_real_http_integration.py` (Policy HTTP réel éphémère sur port 1813, dans `quality.yml` existant). Couverture DEMO/REPLAY/STORY, critic, redondance, seuil, commande REMEDIATE avec booléen HITL forgé, et cas positif au seuil. Aucun nouveau workflow CI.
- Code `48479748dc59a0dd5835818a882bd413edab2ba6` ; tests unitaires `a530ebf3f8cd41098f009830f4912d5adcb99254` ; tests HTTP `871c8da4e1e1d7cc04318caa14d78a8ec09003f6`.

## Contrat et limites
- Endpoint `POST /api/policy/check` et schéma JSON de réponse **inchangés** ; **changement sémantique restrictif** pour les trois modes synthétiques : invalidité Critic/redondance/confiance interdit désormais PASS/SIMULATE.
- `critic_validated`, `redundancy_ok`, `confidence` sont **des assertions de l'appelant**, non des attestations de Critic, d'IA, d'Evidence, de HITL ou de Temporal. `evidence_fresh` reste non exigé dans le chemin synthétique actuel car le worker DEMO ne l'envoie pas ; cela doit rester visible comme **NOT_TESTED**, jamais converti en preuve de fraîcheur. Le worker envoie actuellement des assertions synthétiques `critic_validated=True`, `redundancy_ok=True` ; la correction préserve ce chemin mais n'en vérifie pas la provenance.
- Le comparateur Core/Policy `aiops.demo-policy-unbound-value-crosscheck.v1` reste **NO_GO**, car `POST /api/policy/check` ne lie pas de manière authentifiée `run_id/incident_id` au Run Core. Pas de modification Core/Temporal/Story/NOC/Twin ni d'API tenant.
- Les 7 Runs Debian communiqués par l'utilisateur (5 BLOCKED sans gate, 1 RESOLVED/PASS/SIMULATE, 1 RUNNING ancien) **non revérifiés** : BLOCKED/MISSING ne prouve aucune cause ; RESOLVED/PASS/SIMULATE n'est pas une remédiation LIVE ; RUNNING ne prouve pas de terminaison Temporal. Impact Payments runtime et ai-ledger authentifié : NOT_TESTED.

## CI et vérifications
- [quality.yml PR #40801431389](https://github.com/alimtalbi-ata/aiops/actions/runs/40801431389) : **QUEUED** au premier contrôle sur SHA `871c8da4`.
- [quality.yml push #40801414267](https://github.com/alimtalbi-ata/aiops/actions/runs/40801414267) : **IN_PROGRESS** au premier contrôle sur le même SHA.
- **Ne pas lire ces états comme PASS**. Vérifier les trois jobs et le SHA **final après ce journal** avant toute fusion ; publier la confirmation en commentaire PR et transmettre au lot #156.
- Tests locaux sur copie du dépôt : **NOT_TESTED**. CI finale du commit de journal : **PENDING** à ce stade.
- **NOT_TESTED** : HITL authentifié, Temporal, postchecks, rollback, Evidence E2E, tenant A/B, impact SAN→Payments runtime, déploiement Debian, `applied.sha` authentifié, smoke terrain.

## Release et remise
- **NO-GO E2E ; READY_FOR_STABLE=BLOCKED.** Le déployeur V2 ne copie pas Policy/Core/Twin/Copilot ; le cron n'observe que `refs/heads/deploy/aiops2-stable` et ne valide pas E2E. Aucune modification stable, aucun accès Debian, aucun effet LIVE.
- Handoff à Recette 5/5 #156 pour assemblage, couverture déployeur, tests E2E authentifiés et rollback ; informer NOC #171 et Story #137 du refus Policy synthétique.
- Prochain lot : qualifier le transport de cette version Policy dans un paquet stable complet, puis lier une décision Policy authentifiée au Run/Incident et aux Evidence, sans créer de fausse attestation.
