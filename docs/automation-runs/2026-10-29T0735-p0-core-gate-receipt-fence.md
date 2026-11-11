# P0 Policy/HITL — accusé de gate Core DEMO fail-closed (29/10/2026, créneau 07:35 Paris)

## État vérifié avant changement
- `main`: `27deb9b1a66faf27df8d69b137a63451f7649d80`; `deploy/aiops2-stable`: `e54c4e9a9b37e6229559a1b587c9a06b4741a8b3`. Aucune mutation de ces refs.
- PR candidate existante [#176](https://github.com/alimtalbi-ata/aiops/pull/176), branche `fix/p0-policy-synthetic-critic-fence-20261029-0235`, HEAD de départ `d9476fdeb7633ed7b6d93d36d388cac3c20fd593`. Travail #144→#147→#155→#163 déjà convergé dans `main`, pas de duplication.
- Autres créneaux examinés : #156 Recette, #153 déployeur, #170 Twin, #171 NOC, #169/#177 UI, #137 Story ; journaux `2026-10-29T0431-p0-temporal-synthetic-policy-disposition-fence.md` et `2026-10-29T0636-p0-policy-denial-terminal-core.md`.
- PR historiques #140/#145 : au moins un run CI en échec sur leurs SHA examinés ; #146 : aucun run PR retrouvé. #141 est fusionnée ; #142 ouverte non mergeable ; #143 ouverte ; #144 fermée non fusionnée. Ne pas assembler aveuglément ces branches.

## Livraison verticale unique — refuser un faux acquittement Core
- Défaut P0 : le worker vérifiait la disposition Policy mais ignorait complètement la réponse de `POST /api/runs/{run_id}/gates`. Un HTTP 200 avec `run_id`, `stage` ou `state` incohérent pouvait laisser continuer `STAGE_COMPLETED`, puis un Run synthétique RESOLVED sans confirmation de la gate attendue.
- `app/shared/simulation_policy_contract.py` : `validate_synthetic_gate_receipt` impose les trois champs exacts `run_id`, `stage=POLICY`, `state` identique à Policy, et refuse types/champs/identifiants incohérents.
- `app/worker/main.py` : vérification immédiate de l'accusé Core avant tout traitement `PASS` ou `BLOCKED`. Un accusé ambigu échoue fermé ; il ne peut pas devenir un `PASS/SIMULATE` observé.
- `tests/test_simulation_policy_contract.py` : tests positifs/négatifs du validateur et garde AST d'ordre d'exécution du worker. `tests/test_core_demo_policy_real_integration.py` : vérifie l'accusé du vrai Core HTTP/PostgreSQL 16 éphémère après un refus Policy HTTP.
- Commits code/tests : `5b3d14be8102e2d76bd381a6aa039efac66b0cae`, `ce854ab9faabbbb4dbfa64010a85a10e86371a11`, `466d7ac957f0a891c8204a32c9609385f74d6c34`, `740cc42eac97aba6e7d406668691258e7799c6f6`. CI de ce SHA : [PR #40830302641](https://github.com/alimtalbi-ata/aiops/actions/runs/40830302641) et [push #40830297862](https://github.com/alimtalbi-ata/aiops/actions/runs/40830297862), **IN_PROGRESS** lors de la rédaction initiale ; aucun PASS anticipé.

## Contrats et limites
- API Core `POST /api/runs/{rid}/gates` inchangée : accusé `{run_id,stage,state}`. Contrat interne Worker→Core plus strict ; pas de nouveau workflow CI.
- L'accusé est une confirmation de transport, **pas** une preuve authentifiée de provenance Policy, de `decision`, de l'origine Evidence, de l'isolation tenant, d'un reçu HITL ni de Temporal exécuté. Si la gate a été écrite mais son accusé est ambigu, l'activité échoue ; le Run peut rester RUNNING et exige diagnostic/recette. Le BLOCK de refus et son événement restent non atomiques.
- Historique Debian rapporté (non revérifié) : 7 Runs DEMO, 5 BLOCKED sans gate explicative, 1 RESOLVED/PASS/SIMULATE sans mutation LIVE, 1 RUNNING ancien sans terminaison Temporal attestée. Aucun impact Payments démontré.
- Tests nouveaux : unitaires et HTTP réels en CI **PENDING** au moment de la rédaction ; exécution Temporal réelle, HITL authentifié, tenant A/B, provenance Evidence, E2E ACME, Debian, rollback, `applied.sha` : **NOT_TESTED**. Aucun test serveur exécuté.

## Handoff release
- **READY_FOR_STABLE=BLOCKED ; NO-GO E2E.** Les scripts actuels ne transportent pas automatiquement Worker/Policy/Core/Twin ; la candidate ne doit pas être promue même avec CI verte tant que couverture du déployeur, recette authentifiée, rollback et preuve terrain manquent.
- Seul le schedule 5/5 Recette [#156](https://github.com/alimtalbi-ata/aiops/pull/156) assemble et décide la promotion. Aucun push stable, fusion, SSH Debian, secret ni effet LIVE.
- Prochain lot : exécuter le vrai worker Temporal en sandbox éphémère avec Core/PostgreSQL/Policy, prouver `run_id/incident_id/evidence` sous auth/RBAC et l'absence de faux PASS ; puis remettre au 5/5 le paquet complet et les smoke-tests en lecture seule.


## Qualification CI constatée après rédaction initiale
- SHA code + journal initial `e3bdee7001d1e030f632bc4a7b4e0c15786daafa` : [quality.yml PR #40830365924](https://github.com/alimtalbi-ata/aiops/actions/runs/40830365924) et [push #40830358404](https://github.com/alimtalbi-ata/aiops/actions/runs/40830358404), tous deux **completed/success, 3/3 jobs SUCCESS** sur ce SHA exact. Le SHA de code seul `740cc42eac97aba6e7d406668691258e7799c6f6` a également un push SUCCESS [#40830297862](https://github.com/alimtalbi-ata/aiops/actions/runs/40830297862).
- Logs du push consultés : `test_simulation_policy_contract.py` **12/12 PASS** (dont 2 nouveaux tests de l'accusé Core), `test_policy_safety.py` **18/18 PASS**, `test_core_demo_policy_real_integration.py` **15/15 PASS** (accusé vérifié sur Core HTTP + PostgreSQL 16 éphémères), `test_policy_real_http_integration.py` **12/12 PASS**, `test_core_noc_real_integration.py` **5/5 PASS** ; job Grafana réel SUCCESS. Ces nombres proviennent des logs CI, pas d'un test local ou Debian.
- Ce complément documentaire produit un commit supplémentaire : ses checks doivent être vérifiés séparément. Aucune qualification Temporal exécutée, E2E ACME ou serveur Debian n'est implicite. **READY_FOR_STABLE=BLOCKED** reste la décision.
