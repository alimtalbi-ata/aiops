# 2026-10-28 21:55–21:58 CET — Owner contrats/données ACME — Twin read-only qualifier

## Sources et concurrence
- HEAD `main` vérifié **avant chaque modification de cette branche** : `ec05c89e92a6611922dccbe3690ce1476e3aec92` (PR #141 déjà fusionnée).
- PR ouvertes consultées : #140, #142, #143, #144, #145, #146, #148, ainsi que #153, #155, #156 (poller/stable et recette), #133 (scénario), #139 (NOC), #147 (Policy). Derniers journaux lus : `docs/automation-runs/2026-10-28T2106-p0-acme-twin-path-provenance.md`, documentation Twin direction v1 et script de qualification agrégée `scripts/qualify_acme_readonly.py` sur main.
- Diagnostic PR #142 : sens stocké `consumer(source_id) → dependency(target_id)`; parcours ancien dans ce sens depuis SAN-A = racine seule. PR #142 traverse en inverse. PR #148 expose les arêtes PostgreSQL shortest-hop et transaction read-only. Pas de duplication de ces correctifs.
- PR #142 : SHA `e666ce7a875ce7ee2fbdde6b7a2f35abb1f463f5`, [quality #40744150243](https://github.com/alimtalbi-ata/aiops/actions/runs/40744150243) **completed/success** vérifié (3 jobs). PR #148 : SHA `280166ae1cf1dd475be23ab12c61102706dcdad7`, [quality #40760838278](https://github.com/alimtalbi-ata/aiops/actions/runs/40760838278) **completed/success** vérifié (3 jobs). Étape Twin Docker HTTP + PostgreSQL 16 : SUCCESS dans chaque run. Ces checks ne valent **pas** preuve sur le présent HEAD.

## Livraison
- Nouvelle branche dédiée `feat/p0-twin-acme-readonly-qualification-20261028-2155` basée sur SHA exact #148 `280166ae1cf1dd475be23ab12c61102706dcdad7`. [PR draft #157](https://github.com/alimtalbi-ata/aiops/pull/157), empilée #148 → #142 ; aucune modification des branches des autres créneaux.
- `scripts/qualify_acme_twin_readonly.py` : deux GET loopback seulement, refus anonyme 401, réponse bornée/no-store, comparaison déterministe des 10 nœuds/10 arêtes shortest-hop du seed SQL. Résultat `aiops.acme-twin-readonly-qualification.v1` avec `contract_status=PASS` **topologie seed uniquement**, `overall=NO_GO`, `san_host_link_verified=false`, `runtime_impact_state=UNKNOWN`.
- `tests/test_twin_impact_real_integration.py` : vérification de ce contrat contre le Twin HTTP réel + PostgreSQL 16 éphémères de `quality.yml`, invocation CLI, mutations adversariales (fausses preuves runtime/ACL, fausses arêtes/nœuds, direction), URL hors loopback et refus sans token. Aucun nouveau workflow.
- `docs/demo/ACME-TWIN-READONLY-QUALIFICATION-V1.md` : protocole d'exécution local, exemple JSON, contrat et passage au lot 5/5 Recette.
- Ce journal `docs/automation-runs/2026-10-28T2158-p0-twin-readonly-qualification.md`.
- Commits code `87e26782c5a756ffcbc7cf04c9ead51ebcb06f3a`, tests `469a85f1d7150db2c13c474f064ee2a3fbf93ff3`, contrat `7e6a07efd560815043eac97620d4f9fd5d109577`. Journal : commit ultérieur.
- Contrat Twin existant `GET /api/twin/impact/{node_id}` **inchangé**. Contrat de sortie du nouveau script : `aiops.acme-twin-readonly-qualification.v1` (hors API serveur).

## Vérification et décision
- Checks #142/#148 : SUCCESS vérifié sur SHA exact, pas sur #157. CI #157 : **PENDING** à création du journal ; aucun PASS anticipé.
- Tests locaux : **NOT_TESTED** (édition via connecteur GitHub) ; tests intégration de cette PR : **PENDING** GitHub Actions.
- Seed : 25 nœuds, 23 arêtes. SAN-A → PURE storage → VM-PAY01 → OraclePay → Payments service → business, arêtes E08/E06/E04/E02/E01 ; **aucune arête SAN→hôte**. E10 = VM→RHEL host, SAN-B = dépendance alternative ; ni impact Payments runtime, ni failover démontrés.
- **READY_FOR_STABLE=BLOCKED, GO/NO-GO=NO-GO.** Le cron ne déploie que `deploy/aiops2-stable` ; le déployeur existant ne couvre pas automatiquement `app/twin/main.py` ou ce script. PR #156 couvre le garde-fou de déploiement. Seul le lot 5/5 Recette peut proposer une promotion après checks, compatibilité, rollback et preuve terrain.
- **NOT_TESTED/BLOCKED** : ACL tenant, CMDB authentifiée, Debian, Core→Copilot→Policy SIMULATE→Evidence→Studio E2E, corrélation run/evidence, post-deploy smoke, capture authentifiée, vidéo finale. Aucun SSH, aucun déploiement, aucune mutation LIVE.

## Prochain micro-lot
- Attendre et inspecter les jobs exacts de #157, corriger toute régression ; ensuite remettre au lot 5/5 Recette la chaîne #142→#148→#157 avec SHA final et `NO-GO` maintenu tant que tenant ACL et déploiement Twin ne sont pas qualifiés.
