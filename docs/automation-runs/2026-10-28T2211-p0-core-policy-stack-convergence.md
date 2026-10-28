# 2026-10-28 22:11 Europe/Paris — convergence P0 Core/Policy DEMO

## État et périmètre avant écriture

- `main` revérifié avant la création puis avant le journal : `ec05c89e92a6611922dccbe3690ce1476e3aec92`. `deploy/aiops2-stable` : `e54c4e9a9b37e6229559a1b587c9a06b4741a8b3` ; **non modifiée**.
- PR sources vérifiées : [#144](https://github.com/alimtalbi-ata/aiops/pull/144) HEAD `7c849f40fa1878e2e98a968db11b4fc06f9b79c1` ; [#147](https://github.com/alimtalbi-ata/aiops/pull/147) HEAD `7eaa4c59837f801e83323456ffa87bbb460ed0ea` ; [#155](https://github.com/alimtalbi-ata/aiops/pull/155) HEAD `e9392bae0e7c134541524b242ab04e56100664ce`. Les trois branches sont stables pendant le portage.
- PR ouvertes/branches des autres créneaux examinées : #140–#157, en particulier Twin #142/#148/#157, Studio #143/#145/#150/#152, Evidence #154, Recette #153/#156 ; journaux récents `docs/automation-runs/`, continuité, contrat Core/Policy et `quality.yml`. #141 et #151 sont fermées. Aucun merge de branche de livraison.
- Comparaison GitHub de la base source `793a5a03688dcb7c1a689d07e31bea770da4bd4f` vers `main` : **deux commits**, quatre fichiers uniquement Explore/Story (journal, script `qualify_acme_readonly.py`, test Playwright), disjoints des dix fichiers de la pile Core/Policy. Aucune écriture concurrente écrasée.

## Micro-livraison : un SHA candidat sur main

- Branche dédiée `feat/p0-core-policy-converged-20261028-2211`, [PR draft #160](https://github.com/alimtalbi-ata/aiops/pull/160) **vers main**, commit code/tests/contrats `ea7139570245abaada54164b2a2299bb8c110172`.
- Portage **exact des blobs des dix fichiers** de la pile #144 → #147 → #155 sur l'arbre de `main` (pas de merge massif, pas de réécriture) : `.github/workflows/quality.yml`, `app/core/main.py`, `app/shared/demo_policy_gate_read_model.py`, `scripts/probe_demo_policy_readonly.py`, `tests/test_core_demo_policy_real_integration.py`, deux contrats `docs/demo/ACME-CORE-POLICY-*.md` et trois journaux historiques.
- **Contrat API nouveau par rapport à main :** `GET /api/noc/runs/{run_id}/policy-status`, Bearer **interne**, lecture PostgreSQL DEMO synthétique et fail-closed tenant/chronologie, `aiops.core-demo-policy-observation.v1`. Pas une API viewer tenant qualifiée.
- **Contrat CLI nouveau :** `scripts/probe_demo_policy_readonly.py`, loopback uniquement, GET sans proxy/redirection, même `run_id`/`incident_id`, sortie `aiops.demo-policy-readonly-probe.v1` et `overall=NO_GO` systématique. Pas de preuve de remédiation, HITL ou Temporal.
- **Comportement vérifié par tests :** `BLOCKED/MISSING` n'établit aucune causalité ; `RESOLVED/PASS/SIMULATE` ne prouve aucune exécution LIVE ; `RUNNING` n'atteste aucune terminaison. Rejets de LIVE, identité non concordante, tenant non qualifié, horodatage incohérent, bearer manquant/forgé et fausses attestations.

## Tests et CI authentiquement observés

- Pile source : [quality #40744099485](https://github.com/alimtalbi-ata/aiops/actions/runs/40744099485) (#144), [#40760816940](https://github.com/alimtalbi-ata/aiops/actions/runs/40760816940) (#147), [#40765132813](https://github.com/alimtalbi-ata/aiops/actions/runs/40765132813) (#155) : `completed/success` et trois jobs verts pour chacune, consultés via GitHub.
- **Nouvelle candidate sur main** : [quality.yml #40770102284](https://github.com/alimtalbi-ata/aiops/actions/runs/40770102284), SHA `ea7139570245abaada54164b2a2299bb8c110172`, `completed/success`. Jobs `policy-and-static`, `core-postgres-noc-real-integration`, `grafana-real-integration` tous `completed/success`. Étapes Core PostgreSQL 16 éphémère, démarrage vrai Core HTTP, suite Core/Policy et nettoyage vérifiées `success`. Aucun faux service présenté comme E2E.
- Tests locaux dans ce passage : **NOT_TESTED** ; résultats ci-dessus proviennent de GitHub Actions. CI sur le commit documentaire du présent journal : **PENDING** jusqu'à observation du SHA final.
- **NOT_TESTED** : Debian, les sept Runs rapportés par l'utilisateur, ACL tenant runtime, Policy HTTP, HITL authentifié, Temporal sandbox, postchecks/rollback, Evidence/AI Ledger, chaîne ACME SAN→Payments et vidéo/captures.

## Décision de livraison et risques

- **GO/NO-GO : NO-GO E2E ; READY_FOR_STABLE : BLOCKED.** La PR #160 est une candidate Core/Policy **testée en CI** mais pas une release qualifiée. Les sept Runs (5 BLOCKED, 1 RESOLVED, 1 RUNNING) restent des observations communiquées par l'utilisateur, pas des résultats revérifiés.
- Le déployeur Studio connu copie `demo_v2.py`, `test_demo_v2.py` et injecte `main.py` ; il **ne transporte pas** automatiquement le nouveau module Core, la sonde ou la CI. La PR #156 de Recette confirme un blocage de couverture, et signale une divergence importante entre `main` et la branche stable. Aucun GO sans correction de la couverture, rollback, tests compatibles et preuve `applied.sha` + smoke-test sur Debian par opérateur autorisé.
- Aucune fusion de #144/#147/#155/#160, aucun push stable, aucun accès Debian, aucune commande LIVE, aucun secret ni attestation terrain.

## Prochain micro-lot et handoff 5/5

- Soumettre [PR #160](https://github.com/alimtalbi-ata/aiops/pull/160) au lot Recette 5/5 comme **SHA candidat unique**, vérifier sa CI finale après ce journal et les règles de branche ; coordonner la clôture des PR empilées seulement après intégration qualifiée.
- Recette 5/5 : confronter ce SHA aux contrats Twin #157, Studio #145, Evidence et scripts de déploiement, préparer un paquet complet et une sonde multi-services read-only isolée du poller. Si le déployeur ne couvre pas Core/Twin/Copilot, **BLOCKED** ; ne pas promouvoir `deploy/aiops2-stable`.
- Prochain lot Policy/HITL/Temporal : raccorder une vraie décision HITL authentifiée au Run canonique, puis qualifier Temporal/postchecks sandbox sur services éphémères. Aucun effet LIVE.
