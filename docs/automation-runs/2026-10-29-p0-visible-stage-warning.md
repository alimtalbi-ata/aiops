# 2026-10-29 — P0 raccordement visible de l'avertissement DEMO (5/5)

**Candidat unique : PR #185**, parent `ad05690003ccca919e4cf0cd4a33d495becfaab0` ; base #153 `e5c6b030c374e47f64678f425df78cd147335eec` ; stable `e54c4e9a9b37e6229559a1b587c9a06b4741a8b3`, main `27deb9b1a66faf27df8d69b137a63451f7649d80`. Aucun merge ni push stable, aucun accès Debian, aucun LIVE.

## Blocage UX P0 prouvé, correction REUSE-FIRST

Le 2/5 a démontré sur le parent que `app/portal/demo_v2.py:render_demo_v2` affiche l'avertissement sur les `STAGE_COMPLETED` synthétiques de POLICY/HITL/REMEDIATE/VERIFY, **mais aucune route `/demo-studio/run/{rid}` n'appelle ce renderer**. Les 6 tests unitaires du renderer étaient verts sans preuve d'affichage réel. Dans ce commit, l'avertissement existant est extrait dans `render_stage_marker_warning(detail)` et **réutilisé** dans `render_demo_v2` et dans la route existante `app/portal/main.py:demo_run_detail`, sans nouveau service, endpoint, dépendance ni workflow. Deux tests de route mockée vérifient présence pour POLICY DEMO et absence pour NORMALIZE. La route garde ses événements Core originaux, son viewer Bearer séparé, sa timeline et ses gates ; aucune fausse attestation n'est ajoutée.

## Matrice de livraison / transport

| Besoin | Existant réutilisé | Contrat / lacune | Propriétaire | Transport / rollback |
|---|---|---|---|---|
| Twin SAN→Payments | `app/twin/main.py`, #170 `bec96d2` | Graphe source-backed CI ; impact terrain UNKNOWN | 1/5 | image Twin prévue, terrain NOT_TESTED |
| Core/Evidence/NOC | `app/core/main.py`, `demo_evidence_read.py`, `demo_ledger_read.py`, #171 `a46b5d0` | run/incident/evidence corrélés seulement en contrat ; ACL tenant non attestée | 3/5 | Core+Portal prévues, terrain NOT_TESTED |
| Policy/Worker | `app/policy/main.py`, #176 `b56488d` | SIMULATE CI ; stage marker Worker ≠ décision indépendante | 4/5 | Policy prévue, Worker non transporté |
| Demo Studio | `app/portal/demo_v2.py:render_stage_marker_warning`, `app/portal/main.py:demo_run_detail` | avertissement maintenant raccordé à route ; HTTP réel NOT_TESTED | 2/5 + 5/5 | Portal prévue, rollback terrain NOT_TESTED |
| Release | `deploy/deploy-acme-p0.py:plan,preflight_host`, #153/#185 | poller installé portal-only ; Compose/rollback non qualifiés | 5/5 | **BLOCKED** |

## Tests et gate

Avant ce commit, sur parent `ad05690003ccca919e4cf0cd4a33d495becfaab0` : `quality.yml` run [40905698722](https://github.com/alimtalbi-ata/aiops/actions/runs/40905698722) **6/6 SUCCESS**, quatre workflows et 10/10 check runs SUCCESS. **Ces résultats ne qualifient pas ce nouveau SHA.** Tests ajoutés ici : 2 contrats de route mockée ; **CI du nouveau SHA à vérifier** ; tests locaux, HTTP réel, Debian et rollback : **NOT_TESTED**. Aucun contrat API modifié, uniquement rendu HTML read-only.

**READY_FOR_STABLE=BLOCKED / DEMO_READY terrain=NOT_READY.** Bloqueur principal : poller Debian installé ne transporte que Portal alors que le candidat demande quatre images, et ownership Compose/rollback/applied.sha/smoke sur ce SHA ne sont pas attestés. Action opérateur autorisé, depuis checkout propre au SHA de cette PR : `python3 deploy/deploy-acme-p0.py --stable-sha e54c4e9a9b37e6229559a1b587c9a06b4741a8b3 --candidate-sha "$(git rev-parse HEAD)" --source-dir "$EXISTING_COMPOSE_DIR" --inspect-host` (avec `DOCKER_HOST` et `XDG_RUNTIME_DIR` rootless correctement configurés). Ne pas utiliser `--apply`, ne pas modifier le cron ou les volumes. Résultat `HOST_PREFLIGHT_PASS_UNATTESTED` reste NO_GO.

Le module prep `app/shared/acme_core_evidence_adapter.py` au SHA `a9c850f` n'est **pas intégré** : pure normalisation de fixtures `SYNTHETIC_UNVERIFIED`, sans lecture tenant-scoped ni preuve de run Core. Les 44 tests Debian au SHA `0d7f2ac` ne couvrent pas ce code ni cette PR. #177 UI CI rouge reste exclue.
