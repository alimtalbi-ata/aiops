# 2026-10-29 01:51 Europe/Paris — Recette 5/5, interdiction du bootstrap fictif applied.sha

## Périmètre et SHAs examinés
- Source : PR #153, branche feat/cron-stable-reconciled-20261028, SHA 289d3fc09721ac349b6b0330adf6cbd9e9c33934. PR #156 : 7bd25db12afbb2945c463d3fa35dad16b9c8bcbc.
- HEAD main observé : 27deb9b1a66faf27df8d69b137a63451f7649d80. Stable : e54c4e9a9b37e6229559a1b587c9a06b4741a8b3 ; divergence 43/633 commits, pas de merge aveugle.
- Candidats : UI #169 1c33e459ebf91b525ebdfb696810de6a12ef9bfd ; Twin #170 2318b0bcf8daaae699d7eb7e656b779033c87ce2 ; NOC #171 eb22e022c61e7b3c1d2dd5eb4b85758b5ac89e2e. Checks propres SUCCESS consultés, sans qualification de l'assemblage.
- Branche dédiée : fix/p0-cron-applied-sha-bootstrap-20261029-0151 ; PR cible : feat/cron-stable-reconciled-20261028 (#153). Aucun push stable/main.

## Micro-lot P0 et contrat modifié
- deploy/install-approved-cron.sh ne fabrique plus applied.sha à partir du SHA Git cible et d'un simple tag Docker.
- applied.sha doit être un fichier régulier, non symlink, SHA Git existant exactement sur une ligne ; sa valeur doit égaler la référence stable avant installation du poller. Absence, incohérence ou branche autre que deploy/aiops2-stable : échec AVANT copie du poller et écriture crontab.
- Message NOT_ATTESTED même en cas de correspondance : aucun contrôle indépendant de la machine ou du déploiement. L'opérateur doit produire séparément une attestation réelle et un smoke-test. Ne jamais écrire applied.sha depuis cette recette.
- Sept tests Git/crontab locaux isolés, intégrés à quality.yml existant. Aucun Docker ni crontab hôte.
- API runtime, RBAC, tenant, provenance DEMO/SIMULATED, Policy et LIVE : inchangés. Contrat bootstrap cron fail-closed non auto-attestant.

## Tests et qualification
- Test local hors ligne : python -m unittest discover -s tests -p test_install_approved_cron.py -v : 7/7 PASS ; bash -n deploy/install-approved-cron.sh : PASS.
- GitHub Actions sur SHA candidat : PENDING à la rédaction ; vérifier URL et conclusion sur le commit final et dans la PR avant toute fusion.
- E2E Core→Temporal→Analyst/Critic→Policy SIMULATE→Evidence→Portal, impact Payments, RBAC multi-tenant, rollback Docker Debian, applied.sha terrain, smoke-tests terrain : NOT_TESTED.
- Matrice transport inchangée : demo_v2.py/test_demo_v2.py copiés ; portal/main.py injecté seulement ; Core/Twin/Copilot/Policy/Evidence/SQL non transportés, donc BLOCKED.
- Décision : READY_FOR_STABLE=BLOCKED ; overall=NO_GO.

## Prochain lot
Intégrer ce correctif à #153 après CI verte, puis figer un SHA par domaine et assembler un candidat dont le déployeur transporte/rebuild/restart/rollback chaque module réellement modifié. Exiger CI intégrée, recette read-only, attestation applied.sha et rollback sûr avant toute promotion stable.

## Clôture de convergence 5/5 — 2026-10-29 vers 02:51 Europe/Paris
- PR #175 fusionnée **uniquement dans la branche de développement de #153**, merge SHA `f202ff7b4df0a72d2882af046f51512b940e98dc` ; HEAD source #175 `9ba2845dd9b43678f0ab23504dfaba640d993939`. Ni `main` ni `deploy/aiops2-stable` modifiés. La PR #153 demeure draft et **BLOCKED**.
- Sur le SHA exact #175, `quality.yml` [40796972747](https://github.com/alimtalbi-ata/aiops/actions/runs/40796972747) : **completed/success, 6/6 jobs** ; autres workflows hérités [40796972744](https://github.com/alimtalbi-ata/aiops/actions/runs/40796972744), [40796973585](https://github.com/alimtalbi-ata/aiops/actions/runs/40796973585), [40796972738](https://github.com/alimtalbi-ata/aiops/actions/runs/40796972738) : **completed/success**. Les 7 tests de l'installateur sont inclus dans le job quality-build-package ; aucune recette Docker terrain.
- **CI du SHA de merge et de l'assemblage complet #153 : NOT_VERIFIED à cette écriture** ; les succès de #175 seul ne sont pas transposables automatiquement au merge. Requalifier le SHA final avant tout merge ultérieur.
- Autres candidats consultés : UI #169 `ab7b3385392479f554fc823c47a499f0054ae92a` : `quality.yml` [40799091330](https://github.com/alimtalbi-ata/aiops/actions/runs/40799091330) **FAILURE** (quality-build-package, runtime-e2e), donc **non intégrable** ; Twin #170 `37d4a210f970a8785ae26b2dbedcf378cf368407` : [40797616879](https://github.com/alimtalbi-ata/aiops/actions/runs/40797616879) **SUCCESS** ; NOC #171 `ab91df51b0be2c87773787bb71a4fd932e8501ef` : [40800713203](https://github.com/alimtalbi-ata/aiops/actions/runs/40800713203) **SUCCESS**. Ces CI ne prouvent pas la compatibilité des lignées ni le déploiement.
- `main` `27deb9b1a66faf27df8d69b137a63451f7649d80` ; stable `e54c4e9a9b37e6229559a1b587c9a06b4741a8b3`, **divergence 43/633 commits**. Ne pas fusionner aveuglément.

### Matrice transport réellement observable dans deploy/deploy-demo-studio-v2.sh de #153

| Module candidat | Copie | Build / restart | Tests | Rollback | Qualification |
|---|---|---|---|---|---|
| `app/portal/demo_v2.py` | oui, source portail | image et conteneur portail | unit tests V2 | source et conteneur prévus ; terrain NOT_TESTED | REVIEWABLE sous CI et recette |
| `tests/test_demo_v2.py` | oui, source tests | par effet du rebuild portail | tests V2 | source prévue ; terrain NOT_TESTED | REVIEWABLE |
| `app/portal/main.py` | **injection d'ancre**, pas copie complète | portail seulement | tests portail partiels | source prévue ; terrain NOT_TESTED | BLOCKED pour diff complet |
| Core / Twin / Copilot / Policy / Evidence / Worker / SQL | **non** | **non** | **non dans le déployeur** | **non** | BLOCKED |
| `deploy/*`, `.github/workflows/*` | scripts versionnés mais déploiement/requalification non démontrés | non applicable | CI isolée | non démontré | BLOCKED |

**Risque P0 supplémentaire à traiter** : le poller #153 lit `AIOPS_DEPLOY_BRANCH` sans imposer lui-même `deploy/aiops2-stable`, bien que l'installateur #175 refuse les autres branches. Vérifier et verrouiller ce contrat au niveau du poller avant tout GO. Le poller ne qualifie pas l'E2E.

**Blocage déterminant unique de release** : le déployeur actuel ne transporte pas la chaîne Core/Twin/Copilot/Policy/Evidence nécessaire au scénario SAN→Payments. `READY_FOR_STABLE=BLOCKED`, `overall=NO_GO`. `applied.sha` réel, rollback Docker Debian, auth/RBAC tenant A/B, Policy SIMULATE inter-services, corrélation `run_id/incident_id/evidence_ids`, Impact Payments, logs horodatés et smoke-tests sur SRV-DEB-05 : **NOT_TESTED**. Aucune promotion ni mutation LIVE.

**Prochain acte** : verrouiller la branche au niveau du poller avec tests négatifs, corriger la CI UI #169, figer un SHA par domaine, puis construire un déployeur à couverture complète et rollback transactionnel. L'assemblage ne pourra être qualifié qu'avec `quality.yml` vert sur SHA unique et reçus terrain read-only indépendants du poller.
