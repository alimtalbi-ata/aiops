# 2026-10-29 10:11 Europe/Paris — P0 UI : horodatages Core futurs, chronologie non qualifiée

## Contexte et coordination
- HEAD `main` lu : `27deb9b1a66faf27df8d69b137a63451f7649d80` ; `deploy/aiops2-stable` lu : `e54c4e9a9b37e6229559a1b587c9a06b4741a8b3`. Aucune modification de ces branches.
- PR UI draft [#177](https://github.com/alimtalbi-ata/aiops/pull/177), branche `ui/p0-demo-v2-core-detail-envelope-20261029-0307`, empilée sur [#169](https://github.com/alimtalbi-ata/aiops/pull/169), déjà porteuse des lots UI #140→#150→#152→#158→#166. Aucun nouveau workflow.
- PR #140–#146 consultées : #141 fusionnée, #144 fermée non fusionnée ; #140/#142/#143/#145/#146 encore ouvertes. PR [#170 Twin](https://github.com/alimtalbi-ata/aiops/pull/170), [#171 NOC](https://github.com/alimtalbi-ata/aiops/pull/171), [#176 Policy](https://github.com/alimtalbi-ata/aiops/pull/176), [#153 déployeur](https://github.com/alimtalbi-ata/aiops/pull/153) et [#156 Recette](https://github.com/alimtalbi-ata/aiops/pull/156) relues ; #156 reste BLOCKED malgré les reçus hors ligne #183 intégrés à sa branche.
- Journal précédent UI : `docs/automation-runs/2026-10-29T0907-P0-ui-canonical-ledger-row-identity.md` ; coordination avec Recette 5/5, sans assemblage autonome.

## Une seule livraison verticale P0
- Défaut : `_ordered_events` certifiait « COHÉRENT — ordre par séquence Core » pour des événements monotones mais **datés dans le futur** ; le contrôle de fraîcheur rejetait déjà ces dates, créant deux signaux contradictoires dans Demo Studio V2.
- `app/portal/demo_v2.py` : passe l'horloge UTC de rendu à `_ordered_events` ; un horodatage Core futur invalide désormais la cohérence de la chronologie (`INCONNU`) et interdit toute déduction stale RUNNING. Aucun changement d'endpoint ni de transport, aucun effet LIVE.
- `tests/test_demo_v2.py` : régression négative avec une séquence Core future, contrôle de `Fraîcheur RUNNING — INCONNU`, absence de « COHÉRENT » et de stale ; témoin avec horodatages monotones passés conserve la qualification d'ordre.
- Commits : code `3727575de0d2774f0b1000aca79fefaf2f138cf9`, test `249b663e49ec3a142618c2c26d4a44ead0dc7c2a`. SHA final de cette livraison = HEAD GitHub de la branche après commit du présent journal ; ne pas confondre avec le SHA code/test.

## Vérifications et contrat release
- CI existante `quality.yml` déclenchée automatiquement sur le SHA tests `249b663e` : [run #40847775000](https://github.com/alimtalbi-ata/aiops/actions/runs/40847775000), **IN_PROGRESS** au moment de la rédaction ; **aucun PASS anticipé**. Autres jobs historiques : état à vérifier sur SHA final.
- Tests locaux et Debian : **NOT_TESTED**. Tests navigateur authentifié, tenant RBAC réel, impact ACME SAN→Payments, Core→IA→Policy SIMULATE→Evidence→Portal E2E, rollback, `applied.sha`, smoke-tests et preuve horodatée Debian : **NOT_TESTED**.
- Contrat UI modifié : seulement la **qualification visuelle** de l'ordre Core pour dates futures, de « COHÉRENT » vers « INCONNU ». Contrats Core/Twin/Copilot/Policy/Evidence inchangés. Provenance DEMO/SIMULATED explicite, lecture seule, pas de mutation LIVE.
- Le déployeur [#153](https://github.com/alimtalbi-ata/aiops/pull/153) ne transporte pas de manière prouvée l'ensemble `app/portal/main.py`, Core/Twin/Copilot/Policy/Evidence ; #156 a des contrôles de couverture et reçus offline, **pas d'attestation terrain**. Le cron ne lit que `deploy/aiops2-stable` et ne teste pas les PR. Aucun push stable, fusion ou accès Debian.
- **READY_FOR_STABLE=BLOCKED / NO-GO.** Prochain lot : Recette 5/5 doit vérifier les checks du SHA final, assembler la pile UI avec Twin/NOC/Policy compatibles, qualifier la couverture réelle du déployeur, les tests read-only et rollback, puis seulement envisager une promotion contrôlée.
