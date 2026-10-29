# 2026-10-29 10:24 Europe/Paris — NOC/Copilot P0 : SIMULATE/PASS exige Analysis VALID

## Sources GitHub consultées
- `main` HEAD `27deb9b1a66faf27df8d69b137a63451f7649d80`, `deploy/aiops2-stable` HEAD `e54c4e9a9b37e6229559a1b587c9a06b4741a8b3` (lecture refs GitHub, pas Debian).
- PR NOC consolidée [#171](https://github.com/alimtalbi-ata/aiops/pull/171), base `feat/demo-studio-v2-delivery-20261028`, parent `d13e902dedec056370849ec33e29b8e19236ed83`. La base n'est pas `main` ; compatibilité d'assemblage **NOT_TESTED**.
- PR ouvertes consultées : Recette [#156](https://github.com/alimtalbi-ata/aiops/pull/156) `6cc6679d`, Twin [#170](https://github.com/alimtalbi-ata/aiops/pull/170) `bec96d26`, Policy [#176](https://github.com/alimtalbi-ata/aiops/pull/176) `12fad6c1`, UI [#177](https://github.com/alimtalbi-ata/aiops/pull/177) `a539b293`, déployeur [#153](https://github.com/alimtalbi-ata/aiops/pull/153) `e5c6b030`. Branches `feat/*`, journaux `docs/automation-runs`, commentaires récents de Recette 5/5 et contrat NOC consultés.
- Pile #145→#149→#154→#161→#162→#167 déjà présente dans #171 : aucune nouvelle PR ni duplication. La Recette #156 a intégré #183 seulement dans sa branche et reste NO-GO.
- Migration `db/migrations/009_ai_decision_ledger.sql` : `analysis_records.status` autorise `VALID`, `INVALID`, `UNAVAILABLE`, `SUPERSEDED`. Avant ce lot, la projection vérifiait la Critique validée mais pas le statut de l'Analysis pour `SIMULATE/PASS`.

## UNE livraison verticale P0
- `app/portal/demo_ledger_read.py` : un `SIMULATE/PASS` synthétique ne peut être projeté que si la Critique explicitement liée est `validated=true` **et** son Analysis liée est `VALID`. `INVALID`, `UNAVAILABLE`, `SUPERSEDED` → HTTP 503 `UNKNOWN`, `no-store`, sans IDs/tokens. Les dispositions historiques non réussies restent visibles.
- `tests/test_demo_ledger_read.py` : trois variantes négatives et un cas positif historique `BLOCK/BLOCKED` sur Analysis `SUPERSEDED`. Les tests existants 401-before-I/O, absence d'Evidence, cross-Run/cross-Analysis et Core 401 restent en place.
- Contrat `docs/demo/ACME-PORTAL-LEDGER-EVIDENCE-REFS-V1.md` : règle ajoutée, **aucune modification de forme JSON** `aiops.demo-ledger-read.v1`, pas de changement Core, Twin, Policy, workflow CI, navigateur ou secrets.
- Commits : code `f4398ef4128c094f2622da71fc9bc4d3e2af8ac9`, tests `087a79f7a99b6374b261e826b4d59289f7d6c1d1`, contrat `fb88d15ab2e62a0ca71584c5dd5f779cd67a993e`. SHA journal final à relever après écriture.
- **Limite** : le statut `VALID` est un champ enregistré par Core, pas une preuve de diagnostic IA, d'observation SAN, de causalité Payments ni d'exécution Policy.

## Qualification et décision
- CI existante `.github/workflows/quality.yml` sur nouveau SHA : **PENDING / NOT_TESTED au moment de ce journal** ; ne pas reprendre les checks verts du parent `d13e902d` comme validation de ce changement.
- Tests locaux : **NOT_TESTED** (travail via GitHub connecté, pas de clone local exécuté).
- HTTP Core/Portal/PostgreSQL 16 : tests préexistants, nouveau cas non-VALID persistant **NOT_TESTED** spécifiquement.
- Debian SRV-DEB-05, `applied.sha`, cron et smoke terrain : **NOT_TESTED** ; aucun accès SSH, aucun déploiement, aucune mutation LIVE.
- **READY_FOR_STABLE=BLOCKED / NO-GO** même si la CI NOC devient verte. UI #177 CI rouge (Policy 11/15, E2E non qualifié), projection Policy avec nouveaux IDs incompatible avec validateur exact-key #156, transport déployeur #153 incomplet (Core/Twin/Copilot/Policy/Evidence), tenant A/B, impact Payments observé, E2E métier, rollback et preuves terrain absents.
- Prochain lot **Recette 5/5 uniquement** : adapter la jointure Policy→Critique par ligne, intégrer les candidates en SHA unique, vérifier le transport multi-modules, exécuter quality.yml intégrée, qualifier rollback et smoke read-only, collecter `applied.sha` horodaté. Aucune promotion stable par NOC.
