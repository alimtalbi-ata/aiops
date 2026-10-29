# P0 Policy/HITL/Temporal — refuser PASS/ALLOW dans le worker DEMO (2026-10-29 04:31 Europe/Paris)

## État de départ et coordination

- HEAD `main` observé : `27deb9b1a66faf27df8d69b137a63451f7649d80`. `deploy/aiops2-stable` : `e54c4e9a9b37e6229559a1b587c9a06b4741a8b3` (non modifiés).
- PR de convergence Core/Policy #144 → #147 → #155 → #163 intégrées via #160 et #163 ; #173 et #174 intégrées. Candidate existante [#176](https://github.com/alimtalbi-ata/aiops/pull/176), HEAD initial `ed1103b8b05763797daedd7fda9bc7bedc88c8f4`, CI [PR #40807392992](https://github.com/alimtalbi-ata/aiops/actions/runs/40807392992) et [push #40807387563](https://github.com/alimtalbi-ata/aiops/actions/runs/40807387563) : completed/success sur ce HEAD **antérieur**, pas sur les nouveaux changements.
- PR concurrentes examinées : #156 Recette, #153 déployeur, #170 Twin, #171 NOC/Evidence, #169/#177 UI, #137 Story ; PR historiques #140–#146 non intégrables en bloc. Journaux consultés : `2026-10-29T0004-p0-policy-release-convergence.md`, `2026-10-29T0144-p0-policy-core-unbound-crosscheck.md`, `2026-10-29T0235-p0-policy-synthetic-critic-fence.md`, `2026-10-29T0334-p0-policy-strict-assertion-types.md`, `20261028-1030-hitl-policy-convergence.md`.
- Même branche/PR #176, aucun nouveau workflow, aucune fusion ni push stable.

## Une correction verticale P0

- Défaut dans `app/worker/main.py` : après `POST /api/policy/check`, le worker ne testait que `pol['state'] == 'PASS'`. Une réponse malformée `PASS/ALLOW` (ou `PASS/EXECUTE`) aurait été persistée comme gate PASS Core d'un Run synthétique, malgré l'exigence SIMULATE.
- `app/shared/simulation_policy_contract.py` : ajout de `validate_synthetic_policy_response` qui n'admet que `PASS/SIMULATE`, `BLOCKED/HUMAN_APPROVAL`, `UNKNOWN/HUMAN_APPROVAL`, avec trois clés textuelles exactes et raison non vide. Toute autre forme échoue avant écriture de gate.
- `app/worker/main.py` : validation du retour Policy HTTP **avant** `POST /api/runs/{rid}/gates`. Le chemin d'exception existant écrit `STAGE_FAILED` puis relève l'erreur ; il ne crée pas de gate PASS fictive.
- `tests/test_simulation_policy_contract.py` : refus de PASS/ALLOW, PASS/HUMAN_APPROVAL, BLOCKED/SIMULATE, UNKNOWN/ALLOW, ERROR, corps incomplets, métadonnées supplémentaires, types incorrects ; maintien des trois paires valides et test AST du câblage worker.
- Commits : `51c5948e028e149f15b5f439c76caa61a1ab58e4` (validateur), `d61872908fe10a37a16726d5e91ae8c20fa91b06` (worker), `5686258ac31c6ad902cb82d6767e01bef907dd95` (tests). SHA final à confirmer après ce journal.

## Contrats et vérification

- Contrat externe `POST /api/policy/check` inchangé ; contrat **interne worker → Policy** resserré. Aucun effet LIVE autorisé ; modes DEMO/REPLAY/STORY restent observation/simulation seulement.
- Les tests unitaires `test_simulation_policy_contract.py` sont déjà inclus dans `.github/workflows/quality.yml`. **Nouveaux tests : CI PENDING** au moment de ce journal ; tests locaux, worker Temporal en exécution, HITL authentifié, Core/Policy/Evidence E2E, RBAC tenant A/B, Debian, rollback et `applied.sha` : **NOT_TESTED**. Ne pas extrapoler la CI antérieure.
- Même une gate `PASS/SIMULATE` acceptée ne prouve pas la provenance de la décision : assertions Critic et Evidence fournies par le worker, pas de liaison authentifiée `run_id/incident_id` à Policy. Une réponse non conforme est refusée, pas réparée automatiquement.
- Les 7 Runs DEMO communiqués restent non revérifiés : 5 BLOCKED sans gate ne démontrent pas la cause, 1 RESOLVED/PASS/SIMULATE n'est pas une remédiation LIVE, 1 RUNNING ancien n'atteste pas la fin de Temporal. Impact Payments non démontré.

## Décision et remise à Recette 5/5

- **NO-GO E2E ; READY_FOR_STABLE=BLOCKED**, y compris si `quality.yml` devient vert : le déployeur V2 ne transporte pas automatiquement `app/worker/main.py`, `app/shared/simulation_policy_contract.py`, Core/Twin/Policy ni la recette multi-services. Pas de preuve Debian `applied.sha`/smoke-test ni rollback.
- Recette 5/5 [#156](https://github.com/alimtalbi-ata/aiops/pull/156) est seule responsable de l'assemblage et de la décision de promotion. Remettre SHA final, checks exacts et cette limite de contrat après vérification.
- Prochain lot : lier de manière authentifiée Policy/Run/Evidence, tester Temporal sandbox avec vrai Core/PostgreSQL/Policy éphémères, puis qualifier le paquet, le rollback et les smoke-tests en lecture seule. Aucun accès Debian, aucun secret, aucune mutation LIVE.
