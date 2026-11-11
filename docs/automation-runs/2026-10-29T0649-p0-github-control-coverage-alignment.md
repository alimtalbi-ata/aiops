# 2026-10-29 06:49 Europe/Paris — Recette 5/5, garde .github alignée sur poller

## Inventaire et SHAs vérifiés (GitHub)
- `main`: `27deb9b1a66faf27df8d69b137a63451f7649d80`; `deploy/aiops2-stable`: `e54c4e9a9b37e6229559a1b587c9a06b4741a8b3`, non modifiée.
- PR #153 déployeur (draft, base `feat/demo-studio-v2-delivery-20261028`): `e5c6b030c374e47f64678f425df78cd147335eec`, quality success sur ce SHA. Compare stable→#153: 39 commits ahead, 0 behind, **mais** modifications `app/policy/main.py`, `.github/workflows/*` et scripts deploy non qualifiés pour le transport portail.
- PR #156 recette (draft, base `main`): base du lot `7bd25db12afbb2945c463d3fa35dad16b9c8bcbc`, quality success isolée sur ce SHA; HEAD final de ce lot à vérifier dans la PR et les checks.
- PR #170 Twin: `1f63292e98059c90da9735a365d3e7e9da7ee665`, quality success isolée; #171 NOC/Evidence: `2bb3c69f4bffe4c9ebc46e0f72277e9b33e55875`, quality success isolée; #176 Policy: `d9476fdeb7633ed7b6d93d36d388cac3c20fd593`, quality success isolée.
- PR #169 UI `ab7b3385392479f554fc823c47a499f0054ae92a`, CI rouge signalée; PR #177 UI `004e83298762ebbf2b3ec1264abbc0baefc5eb1d`, quality failure observée. Ces résultats sont propres aux SHA cités et ne qualifient pas leur intégration.
- Journaux précédents consultés : `2026-10-29T0543-p0-poller-workflow-transport-fence.md` (#153), `2026-10-29T0048-p0-stable-transport-matrix.md` (#156), journaux NOC/Twin/Policy du 29 octobre. Aucun assemblage E2E unique qualifié.

## Une livraison verticale P0 : supprimer un faux READY_FOR_REVIEW
Le préflight `scripts/check_demo_stable_coverage.py` autorisait `.github/CODEOWNERS`, `.github/dependabot.yml` et autres fichiers `.github/*` hors workflows comme métadonnées `REVIEWABLE`, alors que le poller #153 refuse **tous** les changements `.github/*`. Ce désaccord produisait un faux accord entre la qualification offline et le cron.

- Changement de contrat `aiops.demo-stable-deployment-coverage.v1` : tous les chemins `.github/*` sont `RELEASE_CONTROL_REQUALIFICATION_REQUIRED`, `decision=BLOCKED`, `copy/rebuild/restart/rollback=NOT_QUALIFIED`. Aucun changement de schéma ou d'API ; `overall=NO_GO` demeure constant.
- Test négatif ajouté dans `tests/test_demo_stable_coverage.py` sur `CODEOWNERS`, `dependabot.yml`, `ISSUE_TEMPLATE`, `workflows`. Le test utilise un vrai dépôt Git local temporaire, sans réseau ni accès Debian.
- CI réutilisée : `.github/workflows/quality.yml` existante, aucun nouveau workflow. **Tests locaux : NOT_TESTED**. Vérifier les jobs sur le HEAD final après push ; ne pas confondre succès CI antérieurs et CI du nouveau SHA.

## Matrice de transport (déployeur #153 observé dans GitHub)
| Chemin candidat | Copie | Rebuild/restart | Tests | Rollback | Verdict |
| --- | --- | --- | --- | --- | --- |
| `app/portal/demo_v2.py` | Source portail | Image et conteneur portail | Tests portail ciblés | Sources et conteneur, non testés terrain | REVIEWABLE uniquement |
| `tests/test_demo_v2.py` | Tests portail | Aucun direct | Tests portail ciblés | Sources, non testé terrain | REVIEWABLE uniquement |
| `app/portal/main.py` | Injection d'ancre, pas copie complète | Portail seulement | Incomplet pour changement arbitraire | Non qualifié | BLOCKED |
| Core / Twin / Copilot / Policy / Evidence / SQL | Aucune | Aucune | Non qualifiés | Aucun | BLOCKED |
| `.github/*` / `deploy/*` | Aucune / contrôle release | Non qualifiés | Requalification requise | Non qualifié | BLOCKED |

## Qualification GO/NO-GO et handoff
- Contrats Core→Temporal→Analyst/Critic→Policy SIMULATE→Evidence→Portal, identité `run_id/incident_id/evidence_ids`, provenance synthetic, tenant RBAC et impact Payments runtime : **NOT_TESTED** en assemblage.
- Vérification `applied.sha` indépendante, smoke-tests SRV-DEB-05, rollback Docker réel et absence de mutation production : **NOT_TESTED** terrain. La sonde `check_demo_field_readonly.py` reste un préflight GET loopback, pas une validation E2E.
- **READY_FOR_STABLE=BLOCKED ; GO/NO-GO=NO-GO**. Ne pas pousser vers stable, ne pas fusionner les PR UI rouges, ne pas déployer Debian ni activer LIVE.
- **Blocage unique** : le déployeur portail ne transporte pas et ne restaure pas la chaîne multi-services retenue.
- **Prochain acte** : le responsable d'assemblage fige un SHA qualifié par domaine, définit un transport/rebuild/restart/rollback multi-services effectivement vérifiable, résout la CI UI, exécute la CI rapide puis complète sur un seul SHA, puis obtient un reçu post-déploiement read-only horodaté et `applied.sha` attesté de l'opérateur avant toute promotion.
