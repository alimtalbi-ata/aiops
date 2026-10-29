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
