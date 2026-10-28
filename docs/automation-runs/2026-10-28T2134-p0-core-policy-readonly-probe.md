# 2026-10-28 21:34–21:38 Europe/Paris — P0 Core/Policy DEMO, sonde locale sans effet

## Vérifications avant écriture

- `main` HEAD vérifié avant branche : `ec05c89e92a6611922dccbe3690ce1476e3aec92` (PR #151 intégrée). HEAD de base #147 : `7eaa4c59837f801e83323456ffa87bbb460ed0ea`, revérifié identique avant création de branche.
- Branches et PR ouvertes inspectées, notamment #133, #137, #140 (Studio 401/403), #142 (Twin impact), #143 (Studio), #144 (Core/Policy), #145 (registre IA), #146 (cron déploiement, **conflit**), #147 (chronologie), ainsi que la PR #141 fermée. Derniers journaux Explore/Story et E2E, `docs/PROJECT-CONTINUITY.md`, protocole de qualification, `quality.yml` et tests Core/PostgreSQL consultés.
- Branche propre `fix/p0-policy-readonly-core-probe-20261028-2134` issue de #147 ; [PR draft #155](https://github.com/alimtalbi-ata/aiops/pull/155) vers #147. Aucune modification de `main` ni des branches des autres lots.
- Données terrain utilisateur **non recontrôlées** : sept Runs Core DEMO (5 BLOCKED, 1 RESOLVED/PASS+SIMULATE, 1 RUNNING ancien), Twin sans impact Payments attesté, AI Ledger 401 sans auth. Aucun appel Debian.

## Micro-livraison verticale et contrat

- `scripts/probe_demo_policy_readonly.py` : GET interne Core en loopback seulement, sans proxy ni redirection, borne 16 KiB, bearer issu de l'environnement non affiché, validation stricte du contrat, identités `run_id`/`incident_id`, provenance et drapeaux d'attestation. Sortie `aiops.demo-policy-readonly-probe.v1`, **toujours `overall=NO_GO`**, date locale non attestée.
- `tests/test_core_demo_policy_real_integration.py` : trois tests supplémentaires avec **vrai Core HTTP + PostgreSQL éphémère CI** (chemin heureux BLOCKED/MISSING, RESOLVED/PASS+SIMULATE, RUNNING ; rejets d'auth, identités, LIVE, chronologie, attestations forgées, URL non-loopback). Les mutations de données ne concernent que les fixtures CI, jamais Debian.
- `docs/demo/ACME-CORE-POLICY-READONLY-PROBE-V1.md` : contrat CLI, exemples, limites et handoff au lot 5/5 Recette. Aucune API serveur ni schéma SQL modifié. Aucun pipeline CI créé : la suite Core/PostgreSQL existe déjà dans `quality.yml`.
- Commits : `4058ea0229e95d0405214c52b653f413ab69684a` (sonde), `5c1a3c6164c71128ec1638291d4626050075d88f` (tests), `d980292faaca5fab416b261420510951678fe6bf` (types fail-closed), `31c6f24dee16f33515f70bbb3de0dd827ae3e377` (contrat), puis commit de ce journal.
- Rollback : fermer la PR, aucun état Core ni schéma modifié.

## CI, statut GO/NO-GO

- Workflow existant [quality.yml #40764752419](https://github.com/alimtalbi-ata/aiops/actions/runs/40764752419), PR sur SHA `d980292faaca5fab416b261420510951678fe6bf` : **IN_PROGRESS au moment de la rédaction** ; aucune revendication PASS.
- [quality.yml push #40764726024](https://github.com/alimtalbi-ata/aiops/actions/runs/40764726024), même SHA : **IN_PROGRESS**.
- CI sur HEAD documentaire final : **PENDING** jusqu'à contrôle GitHub. Tests locaux : **NOT_TESTED**.
- **READY_FOR_STABLE = BLOCKED ; décision = NO_GO.** Le seul test visé concerne Core/PostgreSQL, pas le parcours ACME SAN→Payments→IA→Policy→Evidence→Studio. HITL authentifié, Temporal réel, postchecks, rollback, ACL tenant, AI Ledger, Twin impact Payments, Copilot, Studio terrain et vidéo : **NOT_TESTED**.
- Le script de déploiement Studio existant ne copie pas automatiquement `scripts/probe_demo_policy_readonly.py` ni les nouveaux modules Core ; aucune promotion sur `deploy/aiops2-stable` sans paquet complet, recette E2E, rollback, `applied.sha` et résultat smoke-test serveur authentifié.
- Aucune connexion SSH, aucun déploiement, aucune commande LIVE, aucun secret ni preuve runtime fabriquée.

## Prochain micro-lot et handoff

- Lot 5/5 Recette : consommer la PR #155 **seulement après** convergence ciblée #144/#147, CI finale verte et contrôle des contrats. Assembler les sondes read-only Core/Twin/Copilot/Portal/Evidence dans un protocole isolé du poller ; vérifier sur serveur autorisé les mêmes IDs et les réponses tenant/RBAC, sans remédiation.
- OWNER Policy/HITL/Temporal : poursuivre le raccordement authentifié HITL au Run canonique et tester Temporal sandbox/postchecks sur vrais services éphémères ; ne pas convertir `RESOLVED` en preuve LIVE.
