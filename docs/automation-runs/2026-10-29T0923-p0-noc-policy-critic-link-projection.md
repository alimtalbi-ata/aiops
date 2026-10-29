# 2026-10-29 09:23 CET — NOC P0: liaisons Policy → Critique visibles et vérifiables

## État lu avant modification
- HEAD main `27deb9b1a66faf27df8d69b137a63451f7649d80`; stable `e54c4e9a9b37e6229559a1b587c9a06b4741a8b3`.
- PR NOC unique [#171](https://github.com/alimtalbi-ata/aiops/pull/171), parent `93953c73f96537bc97a24f681fab047edd6d26fe`; quality.yml [#40835353599](https://github.com/alimtalbi-ata/aiops/actions/runs/40835353599) SUCCESS **sur ce parent uniquement** (6/6), pas sur le présent commit.
- PR Recette [#156](https://github.com/alimtalbi-ata/aiops/pull/156) constate explicitement `policy_critic_linkage_origin=NOT_TESTED`: le Portal retire les identifiants de liaison Policy→Critique. Le validateur offline rejette strictement toute clé supplémentaire dans `policy_decisions[]`.
- PR UI [#177](https://github.com/alimtalbi-ata/aiops/pull/177) : quality.yml [#40840178897](https://github.com/alimtalbi-ata/aiops/actions/runs/40840178897) FAILURE (11/15 Policy FAIL), runtime E2E non qualifié. PR Twin [#170](https://github.com/alimtalbi-ata/aiops/pull/170), Policy [#176](https://github.com/alimtalbi-ata/aiops/pull/176) et Recette [#156](https://github.com/alimtalbi-ata/aiops/pull/156) sont des candidates indépendantes, pas un SHA intégré.
- Branches de livraison récentes et `docs/automation-runs` des autres créneaux consultés ; #145/#149/#154/#161/#162/#167 sont déjà convergées dans #171. Aucune nouvelle pile de PR.

## UNE livraison verticale : lien canonique par décision Policy
- `app/portal/demo_ledger_read.py` préserve dans chaque `policy_decisions[]` les champs `analysis_id` et `critique_id` déjà qualifiés par le Portal, y compris `null` si la liaison explicite n'existe pas. Aucun champ de token, prompt, provenance non attestée ou tenant n'est ajouté.
- Test unitaire positif : trois décisions, liaison complète / Analysis seule / Critique seule, avec IDs canoniques exacts ; tests négatifs cross-Run/cross-Analysis/absence de Critique, 401 viewer et Evidence absente existants préservés.
- Test HTTP Core/Portal/PostgreSQL 16 éphémères : vérifie les deux liens dans le cas positif `SIMULATE/PASS` et conserve le refus cross-Run 503.
- Contrat `aiops.demo-ledger-read.v1` **étendu de deux champs par ligne Policy**, sans version bump ; le schéma `aiops.core-demo-evidence-refs.v1` est inchangé.
- **Incompatibilité explicite** : le validateur offline Recette #156 exige exactement trois champs Policy et refusera désormais la projection tant qu'il n'est pas adapté. Ne pas le contourner. Handoff au schedule 5/5 pour vérifier la liaison par ligne, pas seulement « une Critique validée quelque part ».
- Aucune commande LIVE, aucun accès Debian, aucune mutation Core, aucun push stable, aucune fusion, aucun nouveau workflow CI.

## Tests, décisions et limites
- CI sur le nouveau commit : **PENDING / NOT_TESTED** au moment de la préparation ; relever la CI sur le SHA exact et transmettre dans la PR #171 et Recette #156. Aucun résultat antérieur ne qualifie le nouveau code.
- Tests locaux : **NOT_TESTED** (connecteur GitHub, pas de clone exécutable local). Tests terrain Debian : **NOT_TESTED**.
- **READY_FOR_STABLE=BLOCKED / NO-GO**. Dépendances bloquantes : adaptation du validateur #156, quality.yml intégrée verte, CI UI #177 rouge, transport Core/Twin/Portal/Policy par le déployeur, RBAC tenant A/B, impact Payments observé, Temporal/Policy SIMULATE E2E, rollback et `applied.sha` + smoke-tests terrain.
- Prochain lot Recette 5/5 : intégrer cette projection, adapter le validateur exact-key pour vérifier `policy_decisions[].critique_id` contre les Critiques validées du même Run et l'Analysis associée, exiger SHA intégré et CI complète, puis recette read-only/rollback. Aucun GO implicite.
