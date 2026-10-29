# 2026-10-29 01:44 Europe/Paris — P0 Policy/Core : comparaison sans fausse liaison Run

## Base, coordination et état
- HEAD `main` relu avant branche : `64b9f9aa7abae4b35bda2bf881defbe062268bce` (CI push [#40788686239](https://github.com/alimtalbi-ata/aiops/actions/runs/40788686239) completed/success). `deploy/aiops2-stable` : `e54c4e9a9b37e6229559a1b587c9a06b4741a8b3`, non modifiée.
- Branch dédiée `test/p0-policy-core-unbound-crosscheck-20261029-0140`, [PR draft #174](https://github.com/alimtalbi-ata/aiops/pull/174) vers `main`. Coordination : [Recette 5/5 #156](https://github.com/alimtalbi-ata/aiops/pull/156), [Story #137](https://github.com/alimtalbi-ata/aiops/pull/137), [Twin candidate #170](https://github.com/alimtalbi-ata/aiops/pull/170), [NOC candidate #171](https://github.com/alimtalbi-ata/aiops/pull/171), [UI candidate #169](https://github.com/alimtalbi-ata/aiops/pull/169). Piles historiques #140/#142/#143/#145/#146 inspectées ; #141 fusionnée, #144/#147/#155/#163 déjà convergées dans `main` via #160/#163.
- Journaux relus : `2026-10-29T0004-p0-policy-release-convergence.md`, `2026-10-29T0033-p0-policy-real-http-ci.md` et contrat `docs/demo/ACME-CORE-POLICY-OBSERVATION-V1.md`. Aucun merge massif ni changement concurrent écrasé.

## Une micro-livraison verticale mesurable
- `scripts/probe_demo_policy_readonly.py` : `compare_unbound_policy_values` valide l'observation Core DEMO existante, la forme de la décision Policy et l'égalité stricte des valeurs de gate. Refuse identités discordantes, gate absente, LIVE/ALLOW, champs inattendus et types non sûrs. Résultat **toujours** `overall=NO_GO`, `comparison=VALUES_MATCH_NOT_CAUSAL_PROOF`, `policy_run_binding_verified=false`, provenance d'entrée Policy non attestée, aucun secret ni texte `reason` reproduit.
- `tests/test_core_demo_policy_real_integration.py` : test sur **vrais** Policy HTTP (port CI 1813), Core HTTP (1810), PostgreSQL 16 éphémère. Positif `DEMO/PASS/SIMULATE` vs gate persistée, `UNKNOWN/HUMAN_APPROVAL` sans Evidence ; négatifs `BLOCKED`, `RUNNING`, `RESOLVED` sans gate, mauvais incident, faux ALLOW, champs/tokens incohérents, réponse Policy mal typée, et `LIVE/P1/REMEDIATE` bloqué.
- `.github/workflows/quality.yml` : seul le job existant `core-postgres-noc-real-integration` démarre Policy avant les tests Core/Policy ; **aucun workflow supplémentaire**, aucun environnement Debian, aucune commande de remédiation.

## Contrat / interprétation
- Endpoints **inchangés** : `POST /api/policy/check` n'a **pas** de liaison authentifiée `run_id/incident_id` ; `GET /api/noc/runs/{run_id}/policy-status` reste une observation SQL interne. Le nouveau résultat local `aiops.demo-policy-unbound-value-crosscheck.v1` n'est pas un endpoint, ni une preuve que la décision Policy a produit la gate Core. Une égalité de valeurs n'est ni un reçu HITL, ni une exécution Temporal, ni une attestation Evidence ou LIVE.
- Les **7 runs Debian rapportés par l'utilisateur le 28/10** (5 BLOCKED sans gate, 1 RESOLVED avec PASS/SIMULATE, 1 RUNNING ancien) ne sont **pas revérifiés** ici. BLOCKED/MISSING n'explique pas la cause, RESOLVED/PASS/SIMULATE n'atteste pas une remédiation, RUNNING n'atteste pas une terminaison.
- Aucun contrat tenant ACL authentifié de bout en bout ; toute exposition publique du crosscheck serait prématurée.

## Commits, tests et limites
- Commits code/tests/CI : `361b0eeab8f29ab7774e5ae53d877b1f4746c7b6`, `b14d1b60e7c71a6f142970678b3c1e8d4fc1d318`, `f30934f12dd2c054896083ab44ec460d446b3215`, puis durcissement `a3a2182c56b10a07e3c263b73ba72e4825f8f287` et tests `b65a63ede0958e20914d8e654e2cbb1972d43d21`.
- [quality.yml PR #40795698618](https://github.com/alimtalbi-ata/aiops/actions/runs/40795698618), sur `b65a63ede0958e20914d8e654e2cbb1972d43d21` : **completed/success, 3/3 jobs**. Étapes vérifiées : PostgreSQL 16, Core HTTP, Policy HTTP, Core DEMO Policy gate observation (incluant le nouveau crosscheck), Policy SIMULATE/refus LIVE et Grafana réel : SUCCESS.
- Tests locaux : **NOT_TESTED**. CI du HEAD après commit de ce journal : **PENDING**, à vérifier avant toute fusion.
- **NOT_TESTED** : HITL authentifié, Temporal sandbox, postchecks, rollback, Evidence/AI Ledger E2E, ACL tenant runtime, impact SAN→Payments sur Debian, `applied.sha`, smoke-tests terrain.

## Décision / remise
- **NO-GO E2E ; READY_FOR_STABLE=BLOCKED**. La CI des services éphémères ne qualifie ni le runtime Debian ni l'assemblage de release. Le déployeur V2 connu ne transporte pas automatiquement Core/Policy ni cette sonde ; rollback terrain non attesté.
- Prochaine action : vérifier la CI du SHA final de #174 ; remettre au lot Recette 5/5 (#156) pour intégration ciblée après contrôle du déployeur et des contrats. Pour un vrai GO, ajouter plus tard une liaison authentifiée et vérifiable de décision Policy au Run/Incident canonique, un reçu HITL et des preuves Temporal/postchecks/Evidence, sans aucun effet LIVE.
- Aucune promotion stable, aucun accès SSH/Debian, aucune fuite de secret et aucune preuve de déploiement inventée.
