# 2026-10-29 00:04 CET — Release P0 UI, candidate Demo Studio V2

## Base et coordination
- HEAD `main` consulté avant toute modification : `13c455256f34e5e0f0ac55146326888b0fb84c42`.
- Base immuable de travail : PR #166, `925f38fb37d39f9ad0aafd6c30892597e36aedb2`. Chaîne intégrée par ascendance **#140 → #150 → #152 → #158 → #166**, sans merge massif ni modification des branches d'autres owners.
- Branches consultées : `feat/demo-studio-v2-delivery-20261028` `296ab8136efe9a9068cd6b6045236c5abc52694b`, `deploy/aiops2-stable` `e54c4e9a9b37e6229559a1b587c9a06b4741a8b3`. PR ouvertes #140, #142, #143, #145, #146, #150, #152, #153, #156, #158, #166, #168 ; PR #141 et #144 fermées. Documentation de continuité, journal UI #166 et contexte Recette #156 consultés.
- Branche isolée `release/p0-demo-v2-ui-candidate-20261029-0004` ; [PR draft #169](https://github.com/alimtalbi-ata/aiops/pull/169) vers #166. **Ni `main` ni stable modifiés.**

## Micro-livraison verticale : identité Core non ambiguë
- `app/portal/main.py` : `_demo_detail_matches` rejette un `tenant_id` ou `tenant` différent, absent sur une seule projection, vide ou mal typé. `_unique_demo_run` rejette les inventaires comportant plusieurs lignes DEMO/REPLAY/STORY pour le même `run_id` avant tout appel détail/ledger/gates.
- `tests/test_v28_portal_ui.py` : trois tests de non-régression : désaccord/absence de tenant sur SSR et polling, doublons inter-tenants sans I/O supplémentaire, parcours positif avec tenant cohérent et aucune écriture.
- Commits : `dc37e2e8cfe4a850622c733b0bf1823d79ff1e67` (code), `c9f3359eb014b0cc7534c7d420ab6b5dc20004ab` (tests). Aucun nouveau workflow, pas de modification du contrat ACME canonique.
- Contrat public : routes et schémas inchangés ; refus HTTP 404 pour `run_id` d'inventaire ambigu ; SSR `Chronologie Core — INCONNU` et polling `CORE_IDENTITY_UNVERIFIED` en cas de tenant incohérent. **Cette comparaison de métadonnées n'est pas une ACL tenant qualifiée.**

## Tests réellement observés
- [quality.yml GitHub Actions #40784956710](https://github.com/alimtalbi-ata/aiops/actions/runs/40784956710), commit `c9f3359` : logs `quality-build-package` lus ; `test_demo_studio_source_states.py` **5/5 OK**, `test_demo_v2.py` **14/14 OK**, `test_v28_portal_ui.py` **28/28 OK** (dont les trois nouveaux tests, noms vérifiés dans le log). **47/47 tests ciblés in-process OK**.
- Le job `quality-build-package` est **FAIL** : `test_policy_safety.py` **11 échecs / 15 tests**, notamment `AUTONOMY_STATE_UNAVAILABLE`. Ne pas modifier ni contourner le fail-closed pour rendre les assertions vertes. `runtime-e2e` et d'autres jobs étaient encore en cours lors du premier contrôle : résultat final à vérifier, ne pas transférer un statut de job au workflow global.
- Tests locaux : **NOT_TESTED** (clone GitHub indisponible dans le runtime, résolution DNS). Navigateur, Core/PostgreSQL/Temporal intégrés au parcours, tenant ACL runtime, Twin SAN→Payments, Copilot, Policy SIMULATE, Evidence corrélée, captures, rollback, applied.sha Debian : **NOT_TESTED**.

## Release / sécurité
- **Décision : BLOCKED / NO-GO, READY_FOR_STABLE=false.** La CI de #166 était déjà rouge (quality-build-package et runtime-e2e) ; le présent correctif n'en revendique pas la réparation.
- Déployeur `deploy/deploy-demo-studio-v2.sh` observé : copie seulement `app/portal/demo_v2.py`, `tests/test_demo_v2.py` et injecte une ligne dans `app/portal/main.py`. Il ne transporte donc pas les nouvelles fonctions de contrôle d'identité de `main.py` ; compatibilité du paquet **BLOCKED**. La recette #156 vérifie cette couverture, mais son succès ne remplace pas un smoke-test sur Debian.
- Aucun accès SSH/Debian, aucun déploiement, aucune promotion vers `deploy/aiops2-stable`, aucun secret, aucune commande LIVE. Le cron 5 minutes n'applique pas les PR ni les branches `release/*`.
- L'impact Twin vers Payments, les diagnostics IA et les Evidence ne sont pas attestés E2E ; données DEMO/SIMULATED seulement.

## Handoff 5/5 et prochain micro-lot
1. Remettre [PR #169](https://github.com/alimtalbi-ata/aiops/pull/169) à [Recette #156](https://github.com/alimtalbi-ata/aiops/pull/156), avec SHA et couverture de déployeur à corriger, sans promotion automatique.
2. Résoudre les échecs Policy et runtime-e2e avec les owners concernés, exécuter les checks complets sur le SHA candidat final, qualifier la compatibilité `main.py` + `demo_v2.py` avec le déployeur/rollback.
3. Exécuter une recette read-only Core/Twin/Copilot/Portal + navigateur sur services éphémères, puis uniquement après promotion contrôlée obtenir `applied.sha` et smoke-tests authentifiés Debian du lot 5/5. Sinon rester NO-GO.
