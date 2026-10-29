# 2026-10-29 — P0 UI : gates Policy liées au run et tenant Core

## État GitHub vérifié
- `main` HEAD : `27deb9b1a66faf27df8d69b137a63451f7649d80` ; `deploy/aiops2-stable` : `e54c4e9a9b37e6229559a1b587c9a06b4741a8b3`, **non modifiées**.
- Candidate UI existante : [PR draft #177](https://github.com/alimtalbi-ata/aiops/pull/177), branche `ui/p0-demo-v2-core-detail-envelope-20261029-0307`, empilée sur [#169](https://github.com/alimtalbi-ata/aiops/pull/169), qui contient la convergence #140 → #150 → #152 → #158 → #166. Aucune nouvelle PR ni workflow CI.
- PR historiques #140/#142/#143/#145/#146 ouvertes, #141 fusionnée, #144 fermée non fusionnée. Candidates #170 Twin, #171 NOC, #176 Policy et #156 Recette 5/5 lues : résultats indépendants, pas de validation E2E intégrée.
- Journaux consultés : UI 07:12, Recette 07:46, Twin 07:58 et Policy 07:35. #156 a une recette read-only et un comparateur Evidence hors ligne ; #170 atteste un scrape Prometheus/Twin **en CI**, pas une causalité Payments ; #176 vérifie l'accusé Core/Policy mais n'est pas assemblée à l'UI.

## UNE livraison verticale mesurable : empêcher une décision Policy inter-tenant
- Défaut : `verified_policy_gates` vérifiait les `run_id` des items, mais ignorait les `tenant_id`/`tenant` explicites des gates et le `run_id` de l'enveloppe. Une réponse portant une décision PASS/SIMULATE étrangère pouvait être présentée dans la page HTML ou le polling d'un run Core pourtant correctement lié.
- `app/portal/demo_v2.py` : projection fail-closed des enveloppes et items Policy ; toute revendication explicite de `run_id`, `tenant_id` ou `tenant` doit correspondre au run Core vérifié. Les champs de tenant absents des gates restent possibles, **sans attester** une ACL. Le rendu V2 vérifie également les gates lorsqu'il est appelé directement.
- `app/portal/main.py` : la page `/demo-studio/run/{rid}` et le polling `/api/demo-status/{rid}` transmettent désormais l'identité Core vérifiée à la projection. Un conflit produit `UNKNOWN` et ne divulgue aucune justification Policy étrangère.
- `tests/test_v28_portal_ui.py` : deux tests supplémentaires couvrent six formes adversariales (enveloppe run étrangère, tenant étranger, item run étranger, tenant_id/tenant étrangers, liste mixte) et un PASS/SIMULATE légitime de même tenant ; aucun POST. Aucun changement des API Core/Twin/Copilot/Policy/Evidence, ni de contrat LIVE. Seul le contrat de présentation des gates est resserré.
- Commits : `611cf24e6cce68df3509b1da86f14aa137716a3e` (projection), `9512857c01757a75e97f9f72acf765bc846da029` (routes HTML/poll), `14518b0ca9610da8f4f6eb4de43d7c3614795983` (tests). SHA final avec ce journal à relever sur #177 ; **les checks sont propres à chaque SHA**.

## CI réellement observée et NOT_TESTED
- [quality.yml #40833747183](https://github.com/alimtalbi-ata/aiops/actions/runs/40833747183), SHA `14518b0` : logs `quality-build-package` lus. **5/5 tests source-auth, 16/16 Demo V2, 43/43 tests portail : 64/64 PASS**, incluant les deux nouveaux. `static-and-unit` SUCCESS.
- Même SHA : `quality-build-package` **FAILURE**, **11/15 tests Policy FAIL** (assertions historiques dont `AUTONOMY_STATE_UNAVAILABLE`). `runtime-e2e` **IN_PROGRESS** au relevé ; ne pas le déclarer réussi. Les autres jobs terminés observés sont SUCCESS. Aucun contournement ni modification de `quality.yml`.
- Tests locaux : **NOT_TESTED** (checkout indisponible ; accès GitHub par connecteur). Tests navigateur authentifié, tenant A/B en vrai HTTP, source Evidence et corrélation run_id, propagation SAN→Payments, Temporal/IA/Policy/Evidence E2E, déploiement/rollback et `applied.sha` Debian : **NOT_TESTED**.
- La démo Debian historique de 29 tests reste un état **rapporté du 28/10**, pas une qualification de cette candidate.

## Transport, sécurité et remise
- Le déployeur #153 ne transporte pas arbitrairement `app/portal/main.py` ni tous les modules ; ce lot modifie **`main.py` et `demo_v2.py`**. Le script de déploiement doit prouver qu'il embarque les deux versions exactes et leurs tests. #156 doit qualifier transport, contrat de build/restart, rollback et smoke-tests read-only avant promotion.
- **BLOCKED / READY_FOR_STABLE=false / NO-GO** : CI globale rouge, Temporal/E2E non qualifiés, transport et preuve terrain absents. Aucune fusion, aucun push stable, aucun SSH/Debian, aucune remédiation LIVE. DEMO/SIMULATED uniquement ; absence de preuve d'impact Payments explicitement conservée.
- Prochain lot Recette 5/5 : assembler sur un SHA unique les PR #170/#171/#176/#177 compatibles, résoudre les échecs quality.yml et runtime, vérifier la couverture du déployeur et les scripts `check_demo_field_readonly.py` / `check_demo_evidence_receipts.py`, obtenir des preuves opérateur horodatées (`applied.sha`, auth/RBAC, Core/Twin/Copilot/Portal, Policy SIMULATE, Evidence, rollback). Ne pas promouvoir avant les checks verts et l'attestation réelle.
