# 2026-10-29 08:21 CET — NOC/Copilot P0 : SIMULATE/PASS ↔ Critique, qualification HTTP réelle

## État vérifié avant livraison
- `main` : `27deb9b1a66faf27df8d69b137a63451f7649d80` ; `deploy/aiops2-stable` : `e54c4e9a9b37e6229559a1b587c9a06b4741a8b3`. Aucune modification de ces refs.
- PR NOC consolidée [#171](https://github.com/alimtalbi-ata/aiops/pull/171) sur `release/p0-noc-ledger-converged-20261029-0004` (base Demo Studio V2), HEAD initial `805eef167f982ba832f7543a933776b1a9707141`. Ses quatre workflows sur ce SHA : quality.yml, V2.8, Offline et Historical **SUCCESS** (vérifiés dans GitHub).
- Travaux des autres créneaux : [UI #177](https://github.com/alimtalbi-ata/aiops/pull/177) HEAD `b5b098692fa84f6ed5c27ebfa068d193af5a2dd0`, quality.yml [#40833850689](https://github.com/alimtalbi-ata/aiops/actions/runs/40833850689) **FAILURE** (Policy safety et runtime-e2e), trois autres workflows SUCCESS ; [Twin #170](https://github.com/alimtalbi-ata/aiops/pull/170) HEAD `3f14fe28970de39c8f320d123e6121a2459fccd8` ; [Policy #176](https://github.com/alimtalbi-ata/aiops/pull/176) HEAD `766c4cff8bd83566de5e91b2111bf21ca1c07e5e` ; [Recette #156](https://github.com/alimtalbi-ata/aiops/pull/156) HEAD `c391029a1b4aa6a5166a6d835f9a9eb753af96e5`, quality.yml [#40831777965](https://github.com/alimtalbi-ata/aiops/actions/runs/40831777965) SUCCESS isolé.
- Chaîne historique #145 → #149 → #154 → #161 → #162 → #167 déjà portée dans #171 ; pas de nouvelle pile. Lecture de `app/portal/demo_ledger_read.py`, `tests/test_demo_ledger_real_http.py`, `docs/demo/ACME-PORTAL-LEDGER-EVIDENCE-REFS-V1.md` et journaux récents. Le guard `SIMULATE/PASS` exige déjà une Critique validée, mais son test HTTP négatif sur vraies écritures SQL manquait.

## UNE micro-livraison : qualifier le garde Critique sur Core/Portal/PostgreSQL 16
- Commit test : `0b34388a574469dc4c2af728bfa1a425ea7a380f`.
- `tests/test_demo_ledger_real_http.py` : ajout de `test_real_simulate_requires_linked_validated_critique`, deux sous-cas avec **nouveaux Runs DEMO CI** et Evidence, Run-event, Analysis, Critique, Policy `SIMULATE/PASS` persistés en PostgreSQL éphémère append-only :
  1. Critique explicitement `validated=false` mais référencée par Policy ;
  2. Critique `validated=true` dans le Run, mais Policy omet `critique_id`.
- Le test exige Core AI Ledger HTTP 200 et Core Evidence refs HTTP 200 pour montrer que les sources existent, puis Portal viewer HTTP 503 `UNKNOWN`, `no-store`, sans IDs ni jetons. Le cas positif avec Critique liée et validée est déjà couvert par `test_real_policy_foreign_run_links_fail_closed`.
- Contrat API **inchangé** : `aiops.demo-ledger-read.v1`, `aiops.core-demo-evidence-refs.v1` ; lecture seule, token interne exclusivement côté serveur, 401 viewer/Core préservés, `tenant_acl_qualified=false`, `runtime_attested=false`. Pas de modification du workflow existant `quality.yml`.
- Cette qualification teste **des enregistrements synthétiques persistés**, pas un Worker/Policy E2E, pas Ollama, pas les métriques SAN/Payments observées.

## Validation et décision
- Avant cette modification : quality.yml #40828893191 **SUCCESS** sur `805eef167f982ba832f7543a933776b1a9707141` ; les tests du nouveau commit sont **PENDING**, ne pas attribuer le résultat antérieur au nouveau SHA.
- Test local complet : **NOT_TESTED** (pas de clone GitHub local utilisable ; accès GitHub par connecteur uniquement). CI finale : **PENDING** à ce stade, à vérifier sur le SHA documentaire final.
- **READY_FOR_STABLE=BLOCKED / NO-GO**. L'assemblage UI/Twin/NOC/Policy, CI UI rouge, impact Payments observé, tenant A/B authentifié, chemin Temporal/Policy SIMULATE métier, transport Core/Twin/Copilot/Policy par déployeur, rollback, `applied.sha` et smoke-tests Debian restent **NOT_TESTED**.
- Aucun push stable, aucun merge, aucune commande LIVE, aucun accès à SRV-DEB-05. Le poller ne déploie pas les PR et ne prouve pas l'E2E.
- Prochain lot : confirmer le test HTTP et CI complète sur SHA final, transmettre à Recette 5/5 ; seul le schedule 5/5 peut assembler et décider d'une promotion après recette et rollback.
