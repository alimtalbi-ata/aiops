# 2026-10-29 00:04 Europe/Paris — P0 convergence Core/Policy #144 → #147 → #155 → #163

## État vérifié et périmètre

- HEAD `main` vérifié avant écriture : `13c455256f34e5e0f0ac55146326888b0fb84c42` ; PR #160 a déjà porté de manière ciblée #144/#147/#155 dans `main`.
- HEAD de départ de la branche `fix/p0-policy-probe-strict-json-20261028-2233` / [PR #163](https://github.com/alimtalbi-ata/aiops/pull/163) : `a7b3121f66db2f644209d293644f8173d4083c4b`. GitHub indique `mergeable=true`, `mergeable_state=clean`, PR draft avant ce journal.
- `deploy/aiops2-stable` : `e54c4e9a9b37e6229559a1b587c9a06b4741a8b3` ; **aucune modification**, aucune promotion ni accès Debian.
- PR ouvertes et branches des autres créneaux consultées : Recette #153/#156, Story #137, Twin #142/#148/#157/#159/#165/#168, Studio #140/#143/#145/#150/#152/#158/#166, Ledger #149/#154/#161/#162/#167. #141 est fusionnée, #144/#147/#155 sont fermées après portage dans #160 ; #146 reste conflictuelle. Les CI de branches divergentes ne qualifient pas l'assemblage.
- Sources relues : `docs/PROJECT-CONTINUITY.md`, `docs/automation-runs/2026-10-28T2211-p0-core-policy-stack-convergence.md`, journaux #163 du 28/10 à 22:33 et 23:39, `docs/demo/ACME-CORE-POLICY-OBSERVATION-V1.md`, `.github/workflows/quality.yml`, sonde et tests.

## Livraison verticale proposée pour consolidation

- **Une seule candidate Core/Policy** : intégrer les changements de [PR #163](https://github.com/alimtalbi-ata/aiops/pull/163) sur le `main` qui contient déjà #144/#147/#155, uniquement après validation du HEAD final et de la fusion sans conflit. Aucun nouveau workflow ni nouvelle PR.
- Code/tests déjà présents sur la candidate : `scripts/probe_demo_policy_readonly.py` et `tests/test_core_demo_policy_real_integration.py` ; refus JSON à clés dupliquées, valeurs non finies, encodages non UTF-8/BOM, en-têtes HTTP ambigus, sans modifier l'API Core ni autoriser LIVE.
- Contrat `aiops.core-demo-policy-observation.v1` inchangé ; CLI `aiops.demo-policy-readonly-probe.v1` inchangée, validation des entrées plus stricte. `BLOCKED/MISSING` = cause non démontrée ; `RESOLVED/PASS/SIMULATE` = gate simulée persistée, **pas remédiation** ; `RUNNING` = pas de terminaison Temporal attestée. Même `run_id` et `incident_id` exigés.
- Fichiers de #163 : sonde, test Core/PostgreSQL, contrat et trois journaux dont celui-ci. Le présent commit ne modifie que ce journal de qualification ; aucun changement fonctionnel supplémentaire.

## CI et preuves, sans surqualification

- HEAD de code/tests/docs avant ce journal `a7b3121f66db2f644209d293644f8173d4083c4b` : [quality.yml pull_request #40781901252](https://github.com/alimtalbi-ata/aiops/actions/runs/40781901252) **completed/success**, trois jobs `policy-and-static`, `core-postgres-noc-real-integration`, `grafana-real-integration` **success**. Les étapes PostgreSQL 16 réel, Core HTTP réel et tests de gate Core/Policy ont été vérifiées **success** ; tests de rejets JSON/headers sur fixtures, positif Core/PostgreSQL réel. CI push [#40781897209](https://github.com/alimtalbi-ata/aiops/actions/runs/40781897209) rapportée verte dans la PR précédente ; seule la CI PR a été recontrôlée ici.
- **CI du HEAD après le présent journal : PENDING**, à contrôler avant toute fusion ; **CI post-fusion : PENDING** jusqu'à exécution réelle. Tests locaux : **NOT_TESTED**.
- **NOT_TESTED** : Policy HTTP réel, HITL authentifié, Temporal sandbox, postchecks/rollback, Evidence/AI Ledger, ACL tenant runtime, chaîne SAN→Payments, les sept Runs Debian et `applied.sha`. Les sept Runs (5 BLOCKED, 1 RESOLVED, 1 RUNNING) sont des observations utilisateur datées du 28/10, pas des mesures de ce passage.

## Décision, risques et remise à Recette 5/5

- **GO technique Core/Policy conditionnel** aux checks du HEAD final et à la fusion GitHub sans conflit. **NO-GO E2E ; READY_FOR_STABLE=BLOCKED** même si cette convergence est fusionnée sur `main`.
- Le déployeur V2 connu ne copie que `demo_v2.py`, `test_demo_v2.py` et injecte `main.py` ; il ne transporte pas automatiquement Core ni la sonde. Le cron stable n'est ni une recette multi-services ni une preuve E2E.
- Prochaine action : confirmer CI HEAD final, fusionner #163 vers `main` si toutes les protections passent, vérifier le SHA fusionné et CI post-fusion ; transmettre le SHA unique à [Recette #156](https://github.com/alimtalbi-ata/aiops/pull/156). **Seul le lot 5/5** qualifie et décide une éventuelle promotion stable avec couverture complète, rollback et smoke-tests terrain authentiques.
- Aucune commande LIVE, aucun secret, aucun accès SSH, aucun déploiement et aucune prétention d'impact Payments réel.
