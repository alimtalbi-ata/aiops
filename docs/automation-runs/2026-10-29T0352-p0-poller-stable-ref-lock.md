# 2026-10-29 03:52 Europe/Paris — Recette 5/5, verrouillage du poller sur la ref stable

## Observation et provenance
- `main` HEAD lu sur GitHub : `27deb9b1a66faf27df8d69b137a63451f7649d80`.
- `deploy/aiops2-stable` : `e54c4e9a9b37e6229559a1b587c9a06b4741a8b3`; comparaison GitHub `stable...main` = diverged, ahead 43 / behind 633. Pas de merge automatique.
- PR #153 : HEAD `bb7d4af38ba811181e4520a96a008698102ef5b8`, base `feat/demo-studio-v2-delivery-20261028`, draft, CI quality [40803031948](https://github.com/alimtalbi-ata/aiops/actions/runs/40803031948) SUCCESS ; branche de départ de ce correctif.
- PR #156 : `7bd25db12afbb2945c463d3fa35dad16b9c8bcbc`, quality [40790096130](https://github.com/alimtalbi-ata/aiops/actions/runs/40790096130) SUCCESS, mais non intégrée.
- PR #169 UI : `ab7b3385392479f554fc823c47a499f0054ae92a`, quality [40799091330](https://github.com/alimtalbi-ata/aiops/actions/runs/40799091330) FAILURE.
- PR #170 Twin : `930dc4269de541a8cabe424d91c056d00d7e9421`, quality [40803803087](https://github.com/alimtalbi-ata/aiops/actions/runs/40803803087) SUCCESS.
- PR #171 NOC/Evidence : `71818805a4c7077ca88994fe3c70fbaeee3626ed`, quality [40806564328](https://github.com/alimtalbi-ata/aiops/actions/runs/40806564328) SUCCESS.
- PR #140/#142/#143/#145/#146 encore ouvertes ; #141 fusionnée, #144 fermée non fusionnée. Ces branches et leurs tests ne sont pas assimilés à une release unique.
- Documents des autres passages relus : `docs/automation-runs/2026-10-29T0151-p0-cron-bootstrap-attestation.md` (#153), `2026-10-29T0007-p0-poller-coverage-fence.md` (#153) ; matrice #156 consultée via fichiers modifiés.

## Livraison verticale P0
- Branche dédiée `fix/p0-poller-stable-ref-lock-20261029-0352`, basée sur #153, sans écriture dans `main` ou `deploy/aiops2-stable`.
- `deploy/poll-approved-deploy.sh` refuse désormais explicitement toute valeur de `AIOPS_DEPLOY_BRANCH` différente de `deploy/aiops2-stable`, avant mkdir, lock, clone, fetch, checkout et appel au déployeur. L'installateur le refusait déjà ; le poller pouvait encore être invoqué directement avec un environnement modifié.
- `tests/test_poll_approved_deploy.py` ajoute un test négatif paramétré : `feat/unreviewed`, `main`, ref complète, espace final, espaces seuls ; vérifie refus, absence de checkout/lock et absence d'invocation du déployeur.
- Commits code/tests : `d3846b26829ec35b9892e1de98b430d7f8ee17f9`, `f4e4ee87a150ababbced6cf410025d0ecba6cd88`.
- Contrat modifié : **ref unique `refs/heads/deploy/aiops2-stable` pour le poller**. Aucun contrat métier, auth, RBAC, provenance, Policy ou endpoint modifié. Aucun nouveau workflow CI.

## Qualification et matrice de transport
| Module candidat | Copie | Rebuild/restart | Tests | Rollback | Verdict |
| --- | --- | --- | --- | --- | --- |
| `app/portal/demo_v2.py`, `tests/test_demo_v2.py` | oui | portail | unitaires V2 | sources et conteneur prévus, Debian NOT_TESTED | REVIEWABLE |
| `app/portal/main.py` | injection ciblée, pas copie complète | portail seulement | partiels | source prévue | BLOCKED pour diff complet |
| Core/Twin/Copilot/Policy/Evidence/SQL | non | non | non dans le déployeur | non | BLOCKED |
| `deploy/*` et workflows release | non transportés automatiquement | non | CI de contrat | pas de rollback qualifié | BLOCKED |

- Tests de ce correctif : **NOT_TESTED au moment de création du journal** ; `quality.yml` du SHA final doit être observé avant fusion. Les succès #153 sont ceux du parent, pas de cette branche.
- E2E Core→Temporal→Analyst/Critic→Policy SIMULATE→Evidence→Portal, `run_id/incident_id/evidence_ids`, tenant RBAC, Impact Payments, capture authentifiée, `applied.sha` terrain, rollback Docker et smoke-tests SRV-DEB-05 : **NOT_TESTED**.
- La sonde read-only #156 ne vaut pas attestation indépendante ; le poller n'est pas un test E2E.
- Le poller accepte encore `AIOPS_DEPLOY_REMOTE` comme variable d'environnement : hypothèse d'intégrité du cron et de l'environnement à auditer séparément. Le verrou de branche ne qualifie pas à lui seul l'origine du remote.

## Décision et prochain lot
- **READY_FOR_STABLE=BLOCKED ; overall=NO_GO.** Bloquant principal : le déployeur #153 n'assure ni transport ni rollback de la chaîne ACME multi-services. La CI UI #169 est rouge et aucune preuve terrain n'existe.
- Après CI verte de cette PR, l'intégrer exclusivement dans la branche de développement de #153 ; figer un SHA unique par domaine, assembler un déployeur complet, exécuter `quality.yml` sur le SHA assemblé, puis recette read-only terrain avec preuves indépendantes et rollback. Pas de promotion stable ni d'accès Debian.
