# 2026-10-29 01:13 Europe/Paris — P0 UI, fail-closed Policy gates dans Demo Studio V2

## Références vérifiées
- `main` HEAD avant chaque écriture : `64b9f9aa7abae4b35bda2bf881defbe062268bce` ; branche stable `deploy/aiops2-stable` : `e54c4e9a9b37e6229559a1b587c9a06b4741a8b3`, **non modifiée**.
- Base de ce passage : [PR draft #169](https://github.com/alimtalbi-ata/aiops/pull/169), SHA initial `72238006f0eedc69e20aa15f6ed0950497778d8c`, base PR `ui/p0-demo-v2-source-bound-20261028-2314`. Pile existante #140 → #150 → #152 → #158 → #166 → #169 conservée ; aucun merge massif.
- PR ouvertes et créneaux consultés : UI #140/#150/#152/#158/#166/#169, livraison #143, déployeur #153, Recette 5/5 #156, Twin #170, NOC #171, Policy #173 (fusionnée dans main), et anciennes #141/#142/#144/#145/#146. Journal Recette `2026-10-29T0048-p0-stable-transport-matrix.md`, journaux UI #169 et historique `docs/automation-runs/` lus.

## Une micro-livraison P0
- Fichiers : `app/portal/demo_v2.py`, `tests/test_demo_v2.py`, présent journal.
- Commits code `8594e05c1148a9b0e2cce23a6c5b4f7795ace2a1` ; tests `ae8a9ccc2cd9d827e73795222fb6cc62b0f562ac`.
- Contrat **UI seulement**, API Core/Policy inchangée : une enveloppe de gates `status=UNKNOWN`, `error_type` présent, `items` absent/invalide ou contenant des objets non-dict ne doit plus afficher de décisions même si un champ `items` plausible est fourni. Le panneau indique `INCONNU — décisions Policy non vérifiables` ; la vue n'interprète jamais ces éléments comme un PASS/SIMULATE attesté. Une liste de gates valide conserve l'affichage en lecture seule.
- Tests négatifs et non-régression : refus de décisions forgées dans réponses 401/UNKNOWN et listes malformées ; conservation de l'affichage pour `SIMULATE` avec enveloppe valide. Aucun secret, appel LIVE ou écriture métier.

## CI réellement observée
- [quality.yml #40792394479](https://github.com/alimtalbi-ata/aiops/actions/runs/40792394479), SHA **`ae8a9ccc2cd9d827e73795222fb6cc62b0f562ac`** : logs du job `quality-build-package` lus ; **5/5 tests source states, 16/16 tests Demo V2 (dont 2 nouveaux), 29/29 tests UI : PASS (50/50 ciblés)**. Compilation Python PASS.
- Même run : `test_policy_safety.py` **FAIL (11 assertions historiques)**, donc `quality-build-package` FAILURE et CI globale **non verte**. Les autres jobs étaient en cours à l'instant du journal ; aucun PASS global revendiqué.
- [quality.yml #40792372355](https://github.com/alimtalbi-ata/aiops/actions/runs/40792372355) concerne le commit code intermédiaire ; seule la CI du SHA final tests ci-dessus fait foi. Aucun workflow supplémentaire créé ni lancé manuellement.

## Livraison Recette, risques, NOT_TESTED
- **BLOCKED / READY_FOR_STABLE=false / NO-GO**. Le déployeur #153 copie `demo_v2.py` et `test_demo_v2.py`, mais ne transporte pas intégralement les fonctions de `main.py` de #140→#169 ; les correctifs UI de la pile ne sont pas déployables comme ensemble par simple copie. Recette #156 détient la matrice de transport et la décision de promotion.
- `runtime-e2e` sur ce SHA : **PENDING** au journal ; Core/Twin/Copilot/Policy/Evidence réels ensemble, isolation tenant runtime, impact SAN→Payments, navigateur authentifié, captures, rollback et preuve Debian `applied.sha` : **NOT_TESTED**.
- Aucun push stable, aucun accès Debian, aucun déploiement, aucune remédiation LIVE. La présence d'un test unitaire vert n'est pas une attestation terrain.
- Prochain micro-lot : Recette 5/5 doit résoudre la CI Policy/Temporal, assembler la candidate unique avec couverture de transport `main.py` et rollback, exécuter les tests d'intégration et fournir les reçus terrain avant tout GO.
