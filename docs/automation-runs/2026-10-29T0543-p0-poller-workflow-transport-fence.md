# Recette 5/5 — P0 poller GitHub workflow/config transport fence (2026-10-29 05:43 Europe/Paris)

## Références vérifiées (GitHub)
- `main`: `27deb9b1a66faf27df8d69b137a63451f7649d80` (lecture API branche).
- `deploy/aiops2-stable`: `e54c4e9a9b37e6229559a1b587c9a06b4741a8b3` (branche protégée selon API); comparaison stable...main: **diverged**, main 43 ahead / 633 behind.
- #153 déployeur (draft, base `feat/demo-studio-v2-delivery-20261028`): `8ce32211333de89f6536d4c525cd4799d90cd7a1`, checks 16/16 SUCCESS isolés; aucune promotion.
- #156 recette (draft, base `main`): `7bd25db12afbb2945c463d3fa35dad16b9c8bcbc`, checks 6/6 SUCCESS isolés.
- #169 UI `ab7b3385392479f554fc823c47a499f0054ae92a`: quality-build-package et runtime-e2e FAILURE.
- #177 UI `867de3c85f661c592c7ba9ae9be8669fbcf0bc14`: quality-build-package et runtime-e2e FAILURE.
- #170 Twin `01d2a45b10635fc631df6ea117edd960e8f97c78`: 3/3 SUCCESS isolés.
- #171 NOC/Evidence `223fc7ac0be21af54eccb7688937538d73f460e0`: 10/10 SUCCESS isolés.
- #176 Policy `62034bb949f3147dc1498253e847dcd8db1acc8a`: 6/6 SUCCESS isolés.
- #140/#142/#143/#145/#146 ouverts, #141 fusionnée, #144 fermée non fusionnée. Ces états ne qualifient aucun assemblage.
- Consultés: `docs/automation-runs/2026-10-29T0444-p0-poller-approved-origin-fence.md`, scripts #153 et scripts #156, ainsi que `scripts/qualify_acme_readonly.py` de main (recette de contrat simulé, non E2E runtime).

## Livraison verticale unique
- Branche dédiée `fix/p0-poller-workflow-transport-fence-20261029-0543`, créée depuis le HEAD #153; **aucun push stable**.
- Constat: `deploy/poll-approved-deploy.sh` autorisait `.github/*` dans la diff entre `applied.sha` et la branche stable. Les workflows et configurations GitHub n'étaient ni transportés ni exécutés par le déployeur portail. Le préflight #156 les bloque déjà.
- Correctif: suppression de `.github/*` de la liste des chemins autorisés du poller. Tous les changements sous `.github/` sont désormais BLOCKED avant checkout et déploiement. Le contrat des deux fichiers applicatifs copiés demeure inchangé.
- Tests ajoutés: refus d'un changement `.github/workflows/quality.yml` et `.github/dependabot.yml` sur dépôt Git éphémère, vérification absence d'invocation, absence de quarantaine et `applied.sha` inchangé.
- Commits: code `368e0c3542271af1a63a444202de687368b8cf1e`, tests `e015a758d1ac9d69aad2493f6c7382e15aad0508`.
- CI `quality.yml` existante: **PENDING au moment de la rédaction**; ne pas fusionner avant SUCCESS du HEAD exact. Aucun nouveau workflow.
- Contrat modifié: allowlist de chemins du poller, stricte et fail-closed. Aucun contrat Core, Twin, Policy, Evidence, Portal API ou RBAC modifié.

## Matrice de couverture du déployeur actuel
| Module | Copie | Rebuild/restart | Tests | Rollback | Verdict |
|---|---|---|---|---|---|
| `app/portal/demo_v2.py` | oui | portail | régressions V2 prévues | source/conteneur prévu, Debian NOT_TESTED | REVIEWABLE sous conditions |
| `tests/test_demo_v2.py` | oui | non directement | portail | source prévu, Debian NOT_TESTED | REVIEWABLE sous conditions |
| `app/portal/main.py` complet | non, injection ciblée | portail | partiels | source prévu, Debian NOT_TESTED | BLOCKED |
| Core/Twin/Copilot/Temporal/Policy/Evidence/SQL | non | non | CI séparées uniquement | non qualifié | BLOCKED |
| `.github/*` et `deploy/*` | non | non | qualification spécifique nécessaire | non qualifié | BLOCKED |

## Qualification et sécurité
- `READY_FOR_STABLE=BLOCKED`, `overall=NO_GO`. L'absence de transport multi-services reste le **blocker déterminant** pour la promotion.
- Cohérence `run_id` / `incident_id` / `evidence_ids`, provenance synthetic, Core→Temporal→Analyst/Critic→Policy SIMULATE→Evidence→Portal: **NOT_TESTED sur un assemblage réel**. Evidence = référence, pas validation indépendante.
- Tenant RBAC A/B, impact SAN→Payments runtime, rollback Docker, `applied.sha` authentifié, logs, smoke-tests et reçu horodaté Debian SRV-DEB-05: **NOT_TESTED**.
- Le poller est distinct de la recette terrain #156. Aucun accès Debian, aucune mutation LIVE, aucune promotion stable, aucune preuve inventée.
- L'échéance approximative du 29/10 à 05:00 (Paris) est dépassée sans qualification E2E; **NO-GO client**.

## Prochain acte
Vérifier la CI sur le SHA exact de la PR de ce lot; intégrer à #153 seulement après checks verts, puis figer un SHA par domaine et construire un candidat unique avec transport, rebuild/restart, rollback et recette post-déploiement read-only réels. Ne pas pousser sur `deploy/aiops2-stable` sans protections et preuves terrain.
