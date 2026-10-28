# 2026-10-28 22:33 Europe/Paris — P0 sonde Core/Policy JSON strict

## Références et coordination

- `main` au départ et revérifié avant branche : `13c455256f34e5e0f0ac55146326888b0fb84c42` (#160 intégré). `deploy/aiops2-stable` : `e54c4e9a9b37e6229559a1b587c9a06b4741a8b3`, non modifiée.
- Checks historiques #140–#146 examinés : #141 fusionnée avec CI verte ; #142 CI verte mais draft ; #143 CI verte sur sa branche divergente ; #140 et #145 ont aussi des runs en échec parmi plusieurs runs, donc non qualifiées globalement ; #146 sans qualification PR verte et conflit ; #144 fermée après portage. Aucune de ces branches n'est promue automatiquement.
- PR ouvertes et travaux des autres créneaux consultés : #140/#142/#143/#145/#146, #137, #148/#157/#159 (Twin), #149/#154/#161/#162 (Ledger), #152/#158 (Studio), #153/#156 (Recette). #141 déjà fusionnée ; #144/#147/#155 fermées après portage ciblé dans #160. Journal de convergence `2026-10-28T2211-p0-core-policy-stack-convergence.md` et `.github/workflows/quality.yml` lus.
- Branche isolée `fix/p0-policy-probe-strict-json-20261028-2233` issue du SHA `main` ci-dessus. Aucun merge massif, aucun accès Debian ni modification stable.

## Micro-livraison verticale

- `scripts/probe_demo_policy_readonly.py` : parseur strict des réponses Core, refus de clés JSON dupliquées (aussi imbriquées), `NaN`, `Infinity`, `-Infinity`. Une réponse ambiguë est refusée avant projection Policy ; pas de changement de commande, pas d'effet LIVE.
- `tests/test_core_demo_policy_real_integration.py` : test positif du parseur sur réponse **Core HTTP + PostgreSQL 16 réels éphémères** ; six cas négatifs de JSON ambigu/malformé. Les tests existants BLOCKED/MISSING, RESOLVED/PASS/SIMULATE, RUNNING, LIVE, tenant, auth, chronologie restent en place.
- `docs/demo/ACME-CORE-POLICY-OBSERVATION-V1.md` : contrat consommateur strict communiqué aux lots Story et Recette. Pas de modification du schéma API `aiops.core-demo-policy-observation.v1` ni du schéma CLI `aiops.demo-policy-readonly-probe.v1`.
- Commits : `c6bc439637ccf082964f4ff8bac2932bc5e2ad6e` (code), `9af8b5c9e931a68fdfb6c6e0f8d0cb192c74a53d` (tests), `446f1911e1dd3dd2d5aaaf4ef9c6835ef88c074d` (contrat), plus le présent journal.

## Qualification et décision

- Tests locaux : **NOT_TESTED** (pas de services éphémères locaux qualifiés).
- GitHub Actions sur SHA code/tests/docs/journal initial `88b5e3c5bed5fb89216bcfa83cea19e0303c0810` : [quality.yml push #40773104316](https://github.com/alimtalbi-ata/aiops/actions/runs/40773104316) **completed/success**, trois jobs `policy-and-static`, `core-postgres-noc-real-integration`, `grafana-real-integration` `success`. Log du job Core : **12 tests**, dont `test_readonly_probe_strict_json_accepts_real_core_and_rejects_ambiguity ... ok`, sur Core HTTP + PostgreSQL 16 réels. [quality.yml PR #40773126335](https://github.com/alimtalbi-ata/aiops/actions/runs/40773126335) en cours lors de cette mise à jour ; statut final à revérifier. Le commit de mise à jour de journal seul déclenche une nouvelle CI : **PENDING** jusqu'à contrôle de son SHA.
- **NO-GO E2E ; READY_FOR_STABLE = BLOCKED**. Les 7 Runs Debian (5 BLOCKED, 1 RESOLVED, 1 RUNNING) restent des observations utilisateur non revérifiées. `PASS/SIMULATE` n'est pas une remédiation. Twin→Payments, IA/Evidence, ACL tenant, HITL authentifié, Temporal, postchecks, rollback et `applied.sha` sont **NOT_TESTED**.
- Le déployeur V2 actuel ne transporte pas automatiquement le module Core ni cette sonde. La recette 5/5 (#153/#156) seule décide d'une éventuelle promotion après couverture du paquet, CI, smoke-tests et rollback vérifiés ; **aucun push stable**.

## Prochain micro-lot

Faire qualifier par Recette 5/5 le chemin Core→Policy read-only avec le même `run_id`/`incident_id`, puis l'intégrer à une observation multi-services authentifiée et non mutante ; conserver `overall=NO_GO` tant que les preuves E2E manquent.
