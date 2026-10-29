# 2026-10-29 03:22 CET — NOC/Copilot P0 — viewer Bearer malformé refusé avant Core

## Lecture de l'état GitHub avant modification
- `main` HEAD `27deb9b1a66faf27df8d69b137a63451f7649d80` (#174 Policy/Core sans preuve de liaison Run).
- Candidate unique NOC [PR #171](https://github.com/alimtalbi-ata/aiops/pull/171), branche `release/p0-noc-ledger-converged-20261029-0004`, départ `ab91df51b0be2c87773787bb71a4fd932e8501ef`, draft. La CI de ce SHA précédent était verte, mais ne qualifie **pas** le présent correctif.
- Autres créneaux : Recette [#156](https://github.com/alimtalbi-ata/aiops/pull/156) HEAD `7bd25db12afbb2945c463d3fa35dad16b9c8bcbc` (preflight couverture déployeur et `applied.sha`), Twin [#170](https://github.com/alimtalbi-ata/aiops/pull/170) HEAD `930dc4269de541a8cabe424d91c056d00d7e9421`, UI [#169](https://github.com/alimtalbi-ata/aiops/pull/169) HEAD `ab7b3385392479f554fc823c47a499f0054ae92a`, correctif UI [#177](https://github.com/alimtalbi-ata/aiops/pull/177) HEAD `a327c2258572330d3cb8604401411031322b8df3`, Policy [#176](https://github.com/alimtalbi-ata/aiops/pull/176) HEAD `064854a7f56e50a10ebf25d6ccb1bae2848e3681`. PR historiques #140/#142/#143/#145/#146/#149/#154/#161/#162/#167 ouvertes ; ne pas empiler une autre PR. Journaux NOC 02:24 et documents des autres lots consultés.
- La branche stable `deploy/aiops2-stable` est **hors périmètre de mutation**. Le cron ne suit que cette branche, et le déployeur V2 ne transporte pas Core/Twin/Portal hors fichiers explicitement couverts.

## UNE micro-livraison verticale : frontière HTTP viewer avant toute lecture Core
- Défaut repéré dans `app/portal/demo_ledger_read.py` : `hmac.compare_digest(supplied, viewer)` peut lever `TypeError` pour un Bearer Unicode non ASCII, hors du `try` de lecture Core. Une entrée malformée pouvait donc produire 500 au lieu du refus 401 contractuel.
- Correction : refuser avant comparaison les Bearer non ASCII, de longueur >256 ou contenant des espaces/contrôles ; 401 `UNKNOWN/unauthorized`, `no-store`, zéro I/O Core. Aucun jeton interne exposé.
- `tests/test_demo_ledger_read.py` : cas Unicode, surlong et espaces, avec mock qui échoue si Core est contacté.
- `tests/test_demo_ledger_real_http.py` : cas sur un véritable Portal HTTP éphémère (Unicode Latin-1, surlong, espace), absence de fuite d'identifiants et de secrets.
- `docs/demo/ACME-PORTAL-LEDGER-EVIDENCE-REFS-V1.md` : contrat d'entrée resserré, endpoint et schéma `aiops.demo-ledger-read.v1` inchangés.
- Commits de code/tests/contrat : `3808d356124ce7030eb27f38a6b63113fbc44d25`, `92cf88a794b4786476d8608084654126b973a87e`, `43c7f9e8db024b9dd1b7c32fe3448117c39ed5a8`, `0dce0a1be5f64d56456ab2ae183f4f8aa5ff65a4`. Le SHA de ce journal est à lire dans GitHub.

## Qualification et contrat de livraison
- Tests locaux/containers de ce créneau : **NOT_TESTED** ; aucune machine Debian ni base réelle touchée.
- Tests ajoutés à la CI **existante** `.github/workflows/quality.yml` : unitaires et HTTP Core/Portal/PostgreSQL 16 éphémères. Résultat du nouveau HEAD : **PENDING / à consulter** après commit. Aucun nouveau workflow.
- Contrat API : aucune route ou forme JSON changée ; le refus des credentials malformés devient 401, et non 500. Auth viewer distincte du jeton Core ; source `SYNTHETIC_ONLY` et refus tenant restent inchangés.
- **READY_FOR_STABLE=BLOCKED / overall=NO_GO** même si CI verte : absence d'une candidate intégrée UI/Twin/Policy/NOC sur SHA unique, déployeur Core/Portal/Twin non qualifié, ACL tenant A/B non attestée, impact Payments runtime non prouvé, E2E SAN→Payments→IA→Policy SIMULATE→Evidence→Studio **NOT_TESTED**, rollback et `applied.sha` Debian **NOT_TESTED**.
- Aucun push stable, aucune fusion, aucun SSH Debian, aucune mutation LIVE. Handoff exclusif au schedule 5/5 via PR #156.

## Prochain lot
- Vérifier les checks de **ce SHA exact**, documenter le résultat et remettre le SHA à Recette #156.
- Ne pas créer de nouvelles PR NOC ; la Recette 5/5 doit qualifier la couverture du déployeur, l'assemblage et les smoke-tests lecture seule avant toute promotion.
