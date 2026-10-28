# 2026-10-28 23:16 CET — P0 UI, Demo Studio V2 versionné et identité Core

## Références de départ et coordination
- HEAD `main` vérifié avant modification : `13c455256f34e5e0f0ac55146326888b0fb84c42` (convergence Core/Policy #160).
- Base exacte de cette livraison : `2cab29a0fb006838b6591109dd6e75f2e378af86` (PR draft #158), elle-même empilée sur **#140 → #150 → #152**. Aucune branche des autres créneaux modifiée.
- PR et branches récentes consultées : #141 fusionnée (qualification ACME en lecture seule, NO_GO), #142 Twin, #143 livraison V2, #144 portée par #160, #145 ai-ledger, #146 déployeur non fusionnable, #153/#156 Recette, #158 UI, #163 Policy, #165 Twin. Derniers journaux UI #158, Recette #156, Twin #165 et `docs/PROJECT-CONTINUITY.md` consultés.
- Nouvelle branche `ui/p0-demo-v2-source-bound-20261028-2314`, [PR draft #166](https://github.com/alimtalbi-ata/aiops/pull/166) **vers #158**, non vers `main` ; `main` et `deploy/aiops2-stable` inchangés. La comparaison GitHub avec #158 confirme uniquement trois fichiers modifiés, sans merge massif.

## Livraison verticale
Le module `app/portal/demo_v2.py` de la pile #140–#158 était versionné mais **non appelé** dans le `app/portal/main.py` de cette branche ; son insertion dépendait d'une injection locale du script `deploy/deploy-demo-studio-v2.sh`. Ce lot :
- Connecte une fois `render_demo_v2(detail,ledger,gate)` à `/demo-studio/run/{rid}` dans le code versionné. La timeline V2, les états 401/403/UNKNOWN, les séquences Core et la fraîcheur RUNNING deviennent effectivement accessibles via la route existante **lorsque Core fournit une réponse cohérente**.
- Exige l'identité Core réelle imbriquée `detail.run.run_id` et `detail.run.mode` identiques à la liste DEMO/REPLAY/STORY ; vérifie également `incident_id` et `scenario_id` lorsqu'ils sont annoncés dans la liste. En cas de conflit, erreur, format plat ou absence : page `INCONNU` sans lecture des registres Analyst/Critic/Policy et sans affichage des données d'un autre run.
- Applique le même fence au polling `GET /api/demo-status/{rid}` : `status=UNKNOWN`, `source=CORE_IDENTITY_UNVERIFIED`, `events=INCONNU`, registres `UNKNOWN`, sans appels ledger/gates après échec d'identité.
- Réutilise la fonction V2 et le contrat Core existants, sans React ni nouveau endpoint. L'injection historique du déployeur reconnaît déjà la ligne `body+=render_demo_v2(detail,ledger,gate)` et ne doit pas la dupliquer, **mais la compatibilité du déploiement n'est pas qualifiée sur Debian**.

## Fichiers, commits et tests
- `app/portal/main.py` : commit `7b3bbe382f70bda33fb7303b592fb41f9da31eb5`.
- `tests/test_v28_portal_ui.py` : commit `64240715fda5ab38720266b8e76b20267ce5563f` ; trois tests supplémentaires (liaison V2, conflits d'identité SSR et polling) et fixtures historiques corrigées selon le vrai contrat Core `{run:{run_id,mode,...},events:[...]}`.
- `.github/workflows/quality.yml` : commit `65f855edda9d117f2528778e4a13d7c3d2494251` ; la suite V2 de routes est exécutée dans le job existant, aucun workflow parallèle créé.
- **GitHub Actions effectivement observée sur ce SHA code/tests** : [quality #40778726882](https://github.com/alimtalbi-ata/aiops/actions/runs/40778726882). Logs du job `quality-build-package` lus : compilation **SUCCESS**, suites `test_demo_studio_source_states.py` **5/5 OK**, `test_demo_v2.py` **14/14 OK**, `test_v28_portal_ui.py` **25/25 OK**. Ces **44 tests in-process** ne prouvent pas le navigateur ni l'E2E. Le même job **FAIL** ensuite sur **11/15 assertions Policy historiques**, avec `AUTONOMY_STATE_UNAVAILABLE` ; le refus fail-closed n'a pas été affaibli. Jobs migrations PostgreSQL, upgrade et MariaDB **SUCCESS** ; `runtime-e2e` encore en cours au moment du relevé. Les workflows historiques supplémentaires ont été déclenchés automatiquement par `pull_request`, pas manuellement.
- **CI du commit documentaire final** : à contrôler sur le nouveau SHA ; ne pas transférer les 44 OK précédents sans vérification. Aucun test local exécuté, aucun navigateur réel ou service Core/Portal connecté exécuté par ce lot.

## Contrat, sécurité, décision
- Contrat public **route inchangée**, mais sémantique de `GET /api/demo-status/{rid}` renforcée : une réponse Core d'identité incohérente renvoie `UNKNOWN` plutôt qu'un statut d'un autre run. La page SSR ne présente plus les registres après conflit. Provenance DEMO/SIMULATED seulement.
- **NO-GO / READY_FOR_STABLE=BLOCKED.** La pile historique #140→#150→#152→#158 reste divergente de `main`, CI globale non verte, Policy/Temporal non qualifiés ensemble. Les tests UI sont in-process, pas une attestation tenant RBAC.
- **NOT_TESTED** : navigateur authentifié, isolation tenant réelle, Core/Twin/Copilot/Portal éphémères reliés, impact SAN→Payments observé, IA/Policy SIMULATE/Evidence corrélés, preuves horodatées, rollback Docker, `applied.sha`, smoke-test Debian, captures/vidéo. Les arêtes Twin seed sont synthétiques, pas une panne Payments réelle.
- Aucun accès Debian, aucun SSH, aucune mutation LIVE, aucune fusion ni promotion vers `deploy/aiops2-stable`. Le poller 5 minutes n'installe pas les PR `ui/*`; le déployeur actuel ne transporte pas tous les modules requis. **Seul le lot 5/5 Recette** peut assembler et décider une promotion après vérifications.

## Prochain micro-lot et handoff
1. Converger la pile UI en un SHA candidat sur une base compatible avec le déployeur, sans merge massif ; qualifier la route Demo Studio V2 en Chromium isolé avec Core/PostgreSQL éphémères et les réponses d'identité négatives.
2. Résoudre avec le propriétaire Policy les 11 assertions historiques et le job Temporal sans contourner le fail-closed ; relancer `quality.yml` sur le SHA exact.
3. Transmettre [PR #166](https://github.com/alimtalbi-ata/aiops/pull/166) et le présent journal à [Recette 5/5 #156](https://github.com/alimtalbi-ata/aiops/pull/156). Pas de GO sans couverture du déployeur, rollback, recette E2E et attestation `applied.sha` terrain.
