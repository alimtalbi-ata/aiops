# 2026-10-29 07:46 CET — Recette 5/5, corrélation Evidence synthétique hors ligne

## Inventaire GitHub effectivement relu
- HEAD `main`: `27deb9b1a66faf27df8d69b137a63451f7649d80`.
- HEAD `deploy/aiops2-stable`: `e54c4e9a9b37e6229559a1b587c9a06b4741a8b3` (inchangée).
- PR #153 déployeur: `e5c6b030c374e47f64678f425df78cd147335eec`, draft, 16 checks SUCCESS sur ce SHA. Compare stable→#153: 39 ahead/0 behind, mais changements `app/policy/main.py`, `.github/workflows/*` et scripts deploy, hors transport du déployeur portail.
- PR #156 Recette: `293490aae3b8125e2d7b4c8af1f8c9b7762a56a9` au départ, checks verts historiques; un nouveau job a été vu IN_PROGRESS sur ce SHA pendant le contrôle. La présente branche est empilée sur ce SHA, pas sur stable.
- Candidats des autres domaines au contrôle: #170 Twin `1bd173c13f1ae5041ed3d0ec1db483ef04fd399a` (3/3 checks SUCCESS), #171 NOC/Evidence `805eef167f982ba832f7543a933776b1a9707141` (10/10 SUCCESS), #176 Policy `766c4cff8bd83566de5e91b2111bf21ca1c07e5e` (6/6 SUCCESS). #169 UI `ab7b3385392479f554fc823c47a499f0054ae92a` et #177 UI `852f92f08da73d8d1cad4fc2065d44f29e433a30`: quality-build-package FAILURE, runtime-e2e FAILURE, donc BLOQUÉES.
- PR historiques #140/#142/#143/#145/#146 encore ouvertes, #141 fusionnée, #144 fermée sans fusion. Elles ne constituent pas une candidate intégrée qualifiée.
- Journaux consultés: Recette 06:49, NOC/Evidence 02:24, Policy/Core 07:35 et #153 05:43. Les checks de chaque PR sont propres à son SHA.

## Une livraison verticale : comparateur hors ligne Core Evidence ↔ Portal AI Ledger
- Nouveau `scripts/check_demo_evidence_receipts.py` (contrat `aiops.demo-evidence-offline-receipt.v1`) et `tests/test_demo_evidence_receipts.py`.
- Compare **deux exports JSON locaux** issus des contrats existants `aiops.core-demo-evidence-refs.v1` et `aiops.demo-ledger-read.v1`, sans aucun HTTP ni token. Exige le même `run_id`, les classifications `SYNTHETIC_ONLY` et `DEMO_CORE_RECORDED_NOT_LIVE`, l'égalité exacte des références (ID, source, SHA-256 et timestamp), le lien Analysis→Critique→Evidence, des claim checks bornés, et au moins une décision enregistrée `SIMULATE/PASS`. Refuse LIVE/ALLOW, tenant qualifié revendiqué, références étrangères, JSON dupliqué, fichiers symlink finaux et entrées surdimensionnées.
- Réutilise `.github/workflows/quality.yml` existant, un seul step de tests unitaires supplémentaire, aucun workflow nouveau. **Le succès de ce comparateur signifie seulement cohérence référentielle de fichiers fournis par l'opérateur.** Il ne valide ni leur origine, ni les données SAN/Payments, ni l'exécution réelle de Temporal/IA/Policy, ni une ACL tenant.
- Tests locaux dans environnement isolé: `python -m unittest discover -s tests -p test_demo_evidence_receipts.py -v` **7/7 PASS**; `python -m compileall -q scripts tests` PASS. Pas de service réel ni de Debian.
- Commits code `d532f5fecd21f32d628633ed02ce00b82b913b2b`, tests `efbc86faf3ba3a900d030e1a9b76ce3106f0470d`, quality `ba0084cb361813db7d23b8e72ef51166d434f4bd`; borne Evidence 80 `53fb23b6807ae027001a4c0f0dba1fa264ce1ceb`; test 51/81 références `b84f502eb353d6a7235c169cc417a1c5a8953b6c`. Checks du SHA final: **PENDING** au moment de la rédaction; résultats à constater séparément, sans réutiliser ceux de #156.

## Recette opérateur reproductible, lecture seule
Préparer hors dépôt, par un opérateur autorisé, deux exports JSON du **même** Run DEMO à partir des routes de lecture existantes : `GET /api/demo-studio/runs/{rid}/ai-ledger` (Portal, Bearer viewer) et `GET /api/noc/runs/{rid}/evidence-refs` (Core, Bearer interne réservé au serveur). Ne jamais publier les tokens ou les JSON dans Git/CI. Aucun export n'est réalisé par ce script. Sur un poste isolé :

```bash
python scripts/check_demo_evidence_receipts.py \
  --run-id RUN-EXEMPLE-DEMO \
  --ledger-file /chemin/absolu/ledger.json \
  --refs-file /chemin/absolu/refs.json
```

Sortie JSON horodatée UTC sans IDs, chemins, tokens ni données sources; code 0 uniquement pour `REFERENTIAL_CHECK_PASS`, 2 sur `BLOCKED`. `overall=NO_GO` dans tous les cas. Ne pas exécuter le script avec privilèges, ne pas déclencher de mutation. Compléter séparément `scripts/check_demo_field_readonly.py` pour la disponibilité loopback et la correspondance locale `applied.sha`, elle-même non attestée.

## Qualification GO/NO-GO
| Dimension | Statut |
| --- | --- |
| Contrat JSON Core Evidence ↔ Portal Ledger sur fixtures | PASS local, CI PENDING |
| Run/Analysis/Critique/Evidence et SIMULATE enregistré sur services réels | NOT_TESTED |
| `incident_id`, provenance de l'export et indépendance des preuves | NOT_TESTED |
| Tenant RBAC A/B, Temporal, Analyst/Critic indépendants, SAN→Payments runtime | NOT_TESTED |
| Déployeur multi-services copie/rebuild/restart/tests/rollback | BLOCKED |
| Smoke-tests Debian, `applied.sha` attesté et rollback terrain | NOT_TESTED |
| Promotion stable | NO-GO |

**READY_FOR_STABLE=BLOCKED. Blocage déterminant : le déployeur #153 ne transporte pas les composants Core/Twin/Copilot/Policy/Evidence.** Prochain acte: figer un SHA par domaine, assembler un candidat unique sans fusion aveugle de `main` dans stable, construire/qualifier transport et rollback multi-services, exécuter CI intégrée et recette terrain authentifiée. Aucune promotion, aucune modification Debian, aucune remédiation LIVE.

## Clôture du lot #181 (après CI de la PR dédiée)
- PR dédiée [#181](https://github.com/alimtalbi-ata/aiops/pull/181), SHA de tête `deceef411eaebc069fdd0ad11349e52d8be57d57`, fusionnée **uniquement dans la branche Recette #156** au commit `9f59e0593206be7bbbf7d94690692a1743bba66c`. Ni `main` ni `deploy/aiops2-stable` modifiées.
- CI du SHA de tête #181 : [quality.yml PR #40831580652](https://github.com/alimtalbi-ata/aiops/actions/runs/40831580652) et [push #40831588944](https://github.com/alimtalbi-ata/aiops/actions/runs/40831588944), **3/3 jobs SUCCESS chacun** ; logs du job policy-and-static : **7/7 tests Evidence PASS**. CI de fusion sur `9f59e059` : [#40831747759](https://github.com/alimtalbi-ata/aiops/actions/runs/40831747759), **IN_PROGRESS au contrôle**.
- Contrat de sortie inchangé : `overall=NO_GO` même si le comparateur passe. La fusion dans #156 est une intégration de **tests et garde hors ligne**, **pas** une promotion stable ou une qualification E2E.
