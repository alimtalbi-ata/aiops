# 2026-10-29 05:07 Europe/Paris — Release P0 UI : portée Twin racine seule, sans preuve Payments

## Lecture, SHAs et coordination
- HEAD `main` observé : `27deb9b1a66faf27df8d69b137a63451f7649d80`. Stable `deploy/aiops2-stable` : `e54c4e9a9b37e6229559a1b587c9a06b4741a8b3` ; aucune modification stable.
- Branche UI dédiée existante `ui/p0-demo-v2-core-detail-envelope-20261029-0307`, PR draft [#177](https://github.com/alimtalbi-ata/aiops/pull/177) empilée sur [#169](https://github.com/alimtalbi-ata/aiops/pull/169), intégrant la pile #140→#150→#152→#158→#166. Aucun nouveau workflow ni PR parallèle.
- Commits du présent lot : `d6f33dee38113eba5098ace67fc3a2791207e752` (code), `5e41cc49f30c4bfbf4c272b5414b7f7576c24b99` (tests). SHA candidat final = HEAD de #177 après ce journal, à relever sur GitHub.
- PR voisines consultées : #141 fusionnée, #144 fermée sans fusion ; #142/#143/#145/#146, #153 déployeur, #156 Recette, #170 Twin, #171 NOC, #176 Policy et #177 UI ouvertes. Journaux lus : UI `2026-10-29T0414-P0-demo-v2-ledger-identity-projection.md` et Recette `2026-10-29T0048-p0-stable-transport-matrix.md`, `2026-10-28T2350-p0-field-applied-sha-consistency.md`.

## UNE livraison verticale P0
- `app/portal/main.py` : préflight Demo Studio V2 distingue désormais explicitement la réponse Twin **racine seule** (`RACINE SEULE — propagation SAN→Payments NON PROUVÉE`) d'une portée multi-nœuds déclarée (`NON ATTESTÉE`) et des enveloppes invalides/erreurs (`INCONNU`).
- `_demo_impact_scope` refuse les `affected` non-listes, éléments sans `node_id`, doublons, racine absente et enveloppes `UNKNOWN/ERROR/error_type`. Une réponse invalide n'est plus transmise comme impact connu au panneau graphique. Aucun calcul de causalité ni résultat Payments n'est inventé.
- `tests/test_v28_portal_ui.py` : deux tests de non-régression avec cas négatifs et contrôle du HTML + graphe : racine seule malgré une arête SAN→Payments dans le graphe, réponse d'erreur contenant des nœuds forgés, plusieurs nœuds déclarés mais non attestés.
- Contrat API Core/Twin/Policy/Evidence inchangé ; **contrat de présentation** du préflight `Impact SAN-A / Payments` renforcé, labels informatifs sans attestation. Aucun endpoint de mutation, aucune remédiation LIVE.

## Tests, décision, transport
- Tests locaux : **NOT_TESTED** (checkout GitHub non disponible dans le conteneur ; pas de tests Debian). CI existante `.github/workflows/quality.yml` lancée pour le SHA code+tests `5e41cc49` : [run #40816105232](https://github.com/alimtalbi-ata/aiops/actions/runs/40816105232) **IN_PROGRESS** au relevé initial ; ne pas annoncer PASS sans vérification sur SHA final.
- CI précédente PR #177, SHA `851c7ea8` : [run #40811256221](https://github.com/alimtalbi-ata/aiops/actions/runs/40811256221) **FAILURE**, `quality-build-package` (Policy) et `runtime-e2e` rouges ; 56 tests UI ciblés avaient réussi sur ce SHA précédent.
- Transport stable : le déployeur #153 ne copie que `demo_v2.py`, `test_demo_v2.py` et injecte `main.py` partiellement ; ce correctif de `main.py` **n'est pas automatiquement transporté**. #156 doit contrôler transport effectif, rollback et couverture des autres modules. Le poller Debian n'atteste pas E2E.
- **BLOCKED / READY_FOR_STABLE=false / NO-GO** : échéance ~05h dépassée, CI globale antérieure rouge, transport incomplet, recette terrain et rollback non attestés. Aucune fusion, aucun push stable, aucun accès Debian, aucun effet LIVE.
- **NOT_TESTED** : navigateur authentifié, RBAC/tenant runtime, impact réel SAN→Payments, chaîne Core→Temporal→Analyst/Critic→Policy SIMULATE→Evidence→Portal, `applied.sha` authentique, smoke-tests et rollback sur SRV-DEB-05.
- Prochain lot : vérifier CI du SHA final, transmettre à Recette 5/5 la PR #177 avec SHA et NO-GO ; ne promouvoir que si quality.yml intégrale verte, couverture déployeur et rollback qualifiés, recette read-only observée et preuves serveur horodatées.
