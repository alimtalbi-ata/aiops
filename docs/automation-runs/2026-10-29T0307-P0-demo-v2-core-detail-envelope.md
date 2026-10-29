# 2026-10-29 03:07 Europe/Paris — P0 UI : enveloppe Core et événements liés au run

## Lecture et coordination
- HEAD main vérifié : `27deb9b1a66faf27df8d69b137a63451f7649d80`. Stable : `e54c4e9a9b37e6229559a1b587c9a06b4741a8b3` ; inchangée.
- Base UI : PR draft #169 https://github.com/alimtalbi-ata/aiops/pull/169, SHA `ab7b3385392479f554fc823c47a499f0054ae92a` ; pile #140→#150→#152→#158→#166 déjà incluse. Branche isolée `ui/p0-demo-v2-core-detail-envelope-20261029-0307`. SHA candidat = HEAD de la PR dédiée (à vérifier après commit).
- PR ouvertes examinées : #143 V2, #145 Ledger, #146/#153 déploiement, #156 Recette, #169 UI, #170 Twin, #171 NOC, #176 Policy. Journaux UI du 29/10 à 02:12 et Recette 5/5 du 29/10 à 00:48 consultés.

## Une micro-livraison verticale
- `app/portal/main.py` : `_demo_detail_matches` refuse une enveloppe d'erreur Core `UNKNOWN`/`ERROR` ou `error_type` même si elle contient un faux objet `run`. Les événements présents doivent être une liste de dictionnaires ; les identités explicites `run_id` / `tenant_id` / `tenant` doivent correspondre au run. Les événements Core sans ces champs restent compatibles.
- Le refus intervient avant les lectures `/ai-ledger` et `/gates`, ainsi qu'avant le rendu HTML brut et le polling. `/api/demo-status/{rid}` conserve le contrat `status=UNKNOWN`, `source=CORE_IDENTITY_UNVERIFIED`, `events=INCONNU`, `ledger/gates.status=UNKNOWN`.
- `tests/test_v28_portal_ui.py` : deux tests (négatif enveloppe forgée, autre run, autre tenant, événement non-dictionnaire ; positif événement lié). Aucun contrat Core/Twin/Policy modifié, aucun effet LIVE.

## Qualification, risques et remise
- Tests locaux : NOT_TESTED au commit. La CI `.github/workflows/quality.yml` doit être observée sur le SHA final avant toute affirmation de PASS ; aucun workflow additionnel.
- CI précédente PR #169 : https://github.com/alimtalbi-ata/aiops/actions/runs/40799091330 FAILURE (Policy et runtime E2E). 52/52 tests UI ciblés PASS rapportés sur ce SHA précédent, non sur le présent commit.
- **BLOCKED / READY_FOR_STABLE=false / NO-GO** : Policy/Temporal rouge ; déployeur #153 ne transporte pas les changements `main.py` et ne couvre pas le rollback inter-services. PR #156 Recette 5/5 doit qualifier matrice et rollback.
- **NOT_TESTED** : navigateur, auth/RBAC runtime, isolation tenant, SAN→Payments→IA→Policy SIMULATE→Evidence→Portal, rollback, `applied.sha`, smoke-tests Debian. Le poller ne valide pas E2E.
- Prochain lot : Recette 5/5 assemble SHA transportable, CI verte, contrats, recette read-only et rollback avant promotion. Ne jamais pousser stable depuis ce lot.
