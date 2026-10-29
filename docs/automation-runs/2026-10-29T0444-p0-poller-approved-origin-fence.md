# 2026-10-29 04:44 Europe/Paris — Recette 5/5, origine Git du poller verrouillée

## Sources relues / état GitHub observé
- `main` = `27deb9b1a66faf27df8d69b137a63451f7649d80`; `deploy/aiops2-stable` = `e54c4e9a9b37e6229559a1b587c9a06b4741a8b3`. Comparaison GitHub : **diverged**, 43 commits ahead / 633 behind. Aucune fusion aveugle.
- #153 base `feat/demo-studio-v2-delivery-20261028`, HEAD parent `102816664a2f646883871b9868798f41281717e3` ; quality [40809292026](https://github.com/alimtalbi-ata/aiops/actions/runs/40809292026) completed/success (6 jobs), pas de preuve E2E ACME.
- #156 Recette `7bd25db12afbb2945c463d3fa35dad16b9c8bcbc` : quality [40790096130](https://github.com/alimtalbi-ata/aiops/actions/runs/40790096130) success isolée ; garde de transport non intégrée à stable.
- #169 UI `ab7b3385392479f554fc823c47a499f0054ae92a` : quality [40799091330](https://github.com/alimtalbi-ata/aiops/actions/runs/40799091330) **failure**.
- #170 Twin `930dc4269de541a8cabe424d91c056d00d7e9421` : quality [40803803087](https://github.com/alimtalbi-ata/aiops/actions/runs/40803803087) success isolée.
- #171 NOC/Evidence `71818805a4c7077ca88994fe3c70fbaeee3626ed` : quality [40806564328](https://github.com/alimtalbi-ata/aiops/actions/runs/40806564328) success isolée.
- #176 Policy et #177 UI sécurité : ouvertes, non qualifiées dans cet assemblage. Sources historiques #140/#142/#143/#145/#146 ouvertes, #141 fusionnée, #144 fermée non fusionnée (état précédemment documenté).
- Journaux des autres créneaux consultés : `2026-10-29T0352-p0-poller-stable-ref-lock.md` et `2026-10-29T0151-p0-cron-bootstrap-attestation.md`, contrats #153/#156 et scripts du déployeur.

## Unique livraison P0 de ce passage
- Branche dédiée `fix/p0-poller-remote-origin-fence-20261029-0444`, issue du HEAD exact #153, **pas de push stable**.
- Le poller permettait de surcharger `AIOPS_DEPLOY_REMOTE` avec un dépôt arbitraire contenant la même branche `deploy/aiops2-stable`. La vérification de branche seule ne garantit donc pas l'origine du code.
- `deploy/poll-approved-deploy.sh` refuse maintenant toute origine autre que **exactement** `git@github.com:alimtalbi-ata/aiops.git` ou `https://github.com/alimtalbi-ata/aiops.git`, avant création du lock, clone ou fetch.
- `tests/test_poll_approved_deploy.py` exerce la véritable logique Bash avec un shim Git **limité au test** redirigeant uniquement le clone de l'origine officielle vers un dépôt Git éphémère local. Tests négatifs sur 6 remotes non approuvés, test positif HTTPS ; les tests de non-fast-forward, quarantine, coverage et applied.sha existants sont conservés. Aucun mode de contournement ajouté au script de production.
- Contrat modifié : origine Git de déploiement autorisée à deux URL exactes ; branche stable unique inchangée. Pas de changement de contrat Core/Twin/Policy/Evidence ni de workflow CI.
- Commits code/tests : `a89b236ee3d61447ef40c47f76ee24a7269a0697`, `34b985e4f066633c5b489ac4d64d651df5815754`, `ee4136dd9a3a5d8b80cdb14239c5ccec4571a187`.
- Tests et checks sur SHA de livraison : **PENDING** à la rédaction. Ne pas fusionner avant qualité verte.

## Matrice de transport de la release visée
| Domaine | Copie | Rebuild/restart | Tests | Rollback | Décision |
| --- | --- | --- | --- | --- | --- |
| `app/portal/demo_v2.py` + `tests/test_demo_v2.py` | Copie ciblée | Portal uniquement | V2 ciblés | Source + conteneur prévus, terrain NOT_TESTED | REVIEWABLE seulement |
| `app/portal/main.py` complet | Injection d'ancre uniquement | Portal | Partiels | Source prévu | BLOCKED |
| Core/Temporal/Analyst/Critic/Policy/Evidence/Twin/Copilot/SQL | Aucun transport qualifié | Aucun restart qualifié | CI isolées, pas E2E | Aucun rollback qualifié | BLOCKED |
| Scripts deploy / workflows release | Pas de transport automatique qualifié | Non qualifié | Tests Git hors ligne | NOT_TESTED terrain | BLOCKED |

## Qualification GO/NO-GO
- Sécurité de l'origine Git : **PENDING CI**, même si les tests deviennent verts cela n'atteste pas le remote réel Debian ni la protection de branche GitHub.
- Cohérence `run_id` / `incident_id` / `evidence_ids`, provenance SYNTHETIC, liaison Core→Temporal→Analyst/Critic→Policy SIMULATE→Evidence→Portal : **NOT_TESTED comme E2E assemblé**. Evidence = références, pas validation indépendante.
- Tenant RBAC A/B authentifié, impact Payments runtime, rollback Docker sur SRV-DEB-05, `applied.sha` authentifié, logs et smoke-tests post-déploiement : **NOT_TESTED**.
- Le poller ne réalise pas la recette E2E. La sonde read-only #156 conserve `overall=NO_GO` même si ses probes passent. Aucune remédiation LIVE, aucun accès Debian.
- **READY_FOR_STABLE=BLOCKED ; overall=NO_GO**. Le blocage déterminant reste l'absence d'un déployeur multi-services transportant réellement les modules du candidat intégré et leur rollback.

## Prochain acte
Après CI verte sur le SHA exact, remettre ce correctif à #153, puis figer une candidate unique par domaine et qualifier le déployeur couvrant tous les fichiers avant CI intégrée et recette post-déploiement read-only. Ne jamais promouvoir `deploy/aiops2-stable` sans checks verts, protections, rollback et reçus terrain.

## Clôture CI et intégration ciblée (04:48 Europe/Paris)
- PR [#179](https://github.com/alimtalbi-ata/aiops/pull/179), SHA exact de livraison `aca680d2e25efbc8c672580737df751fbfdb08fa`.
- [quality.yml #40813964971](https://github.com/alimtalbi-ata/aiops/actions/runs/40813964971) **completed/success**, **6/6 jobs SUCCESS**. Logs du job `quality-build-package` `123250576432` consultés : **12/12 tests poller PASS** (dont refus des six remotes et positif HTTPS), **7/7 installateur PASS**, **4/4 rollback-name PASS**.
- Workflows hérités sur le même SHA : [V2.8 #40813965075](https://github.com/alimtalbi-ata/aiops/actions/runs/40813965075), [Offline #40813964987](https://github.com/alimtalbi-ata/aiops/actions/runs/40813964987), [Historical #40813965083](https://github.com/alimtalbi-ata/aiops/actions/runs/40813965083), tous **completed/success**.
- PR #179 fusionnée **uniquement dans la branche de développement de #153**, merge SHA `66f7b9776f7b533230541674302ab92e9e558b1a` après contrôle du HEAD, de la base et des checks verts. `main` et `deploy/aiops2-stable` inchangées par cette fusion.
- Le contrôle de remote est une **allowlist de chaînes**, pas une attestation cryptographique de l'hôte Debian ; configuration Git locale `url.*.insteadOf`, clés SSH, certificat TLS, permissions et origine du cron restent **NOT_TESTED**.
- CI post-merge et CI du commit de clôture documentaire : **PENDING** au moment de cette écriture. **READY_FOR_STABLE=BLOCKED / NO-GO** inchangé.
