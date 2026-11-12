# AIOPS2 — audit différentiel du contrat bootstrap navigateur (2026-11-11 08:12 Europe/Paris)

## Provenance / portée
Source GitHub `main`, `app/portal/portal_bootstrap_client.js` blob `ac58f73c725f5e088081bffed4478ea18585ef5c`, et `app/portal/main.py` consultés le 2026-11-11. **SOURCE uniquement**, aucune preuve de correspondance image↔commit. Références v28/V145, fs1073/fs1051/fs621, portail actif 7777 et candidat 17778 : contrats HTTP/DOM **UNKNOWN**. Inventaire rootless communiqué par l'opérateur (UID 1001, socket `/run/user/1001/docker.sock`, 87 conteneurs/210 images) : preuve historique du faux diagnostic rootful #557, pas reçu frais. **DEBIAN UNKNOWN ; E2E NON VÉRIFIÉ.**

## Matrice avant/après, risque et restauration
| Route / capacité | v28/V145/fs* (avant) | Source actuelle (après candidat GitHub) | Actif 7777 / candidat 17778 | Cause potentielle / priorité | Recette / restauration autorisée |
|---|---|---|---|---|---|
| `GET /api/portal/bootstrap` dashboard | UNKNOWN | serveur 503 `TENANT_ACL_NOT_QUALIFIED` même viewer ; client rejette enveloppe sans ACL serveur | UNKNOWN / UNKNOWN | fausse lecture tenant ou chiffres non attestés / P0 | maintenir 503/UNKNOWN ; aucune réactivation bearer-only |
| `GET /api/portal/bootstrap` Core/Twin/Runs | UNKNOWN | client exige `tenant_acl_qualified=true`, `actor_identity_server_derived=true`, états stricts ; limite 100 Runs | UNKNOWN / UNKNOWN | enveloppe falsifiée, lecture croisée / P0 | fixture négative, aucune mutation ni appel amont |
| `GET /` navigation et UX | UNKNOWN | shell Runs/Twin/Copilot/NOC/GLPI, état initial UNKNOWN ; effacement token immédiat | UNKNOWN / UNKNOWN | fuite token ou données obsolètes / P0 | recette DOM et annulation des requêtes périmées |
| `GET /api/portal/components` NOC/GLPI | UNKNOWN | 503 ACL tenant non qualifiée | UNKNOWN / UNKNOWN | fuite d'URL opérateur / P0 | préserver fail-closed |
| `POST /api/copilot` | UNKNOWN | 503 sans ACL qualifiée | UNKNOWN / UNKNOWN | question transmise hors tenant / P0 | préserver fail-closed |
| Evidence/NOC, visualisation | UNKNOWN | aucun succès LIVE inférable du bootstrap | UNKNOWN / UNKNOWN | confusion READABLE_UNVERIFIED/LIVE / P1 | afficher UNKNOWN ou READABLE_UNVERIFIED seulement selon contrat |

## Recette négative isolée à exécuter hors production
Avec DOM synthétique et `fetch` simulé, sans réseau ni secrets, appeler `loadPortalReadModel()` avec jeton fictif ; répondre HTTP 200 avec une enveloppe `schema=aiops.portal.readmodels.v1`, `provenance=UNATTESTED_UPSTREAM_API_READ`, `states.dashboard=READABLE_UNVERIFIED`, `dashboard.open_p1=9`, mais `tenant_acl_qualified=false` **ou** `actor_identity_server_derived=false`. Attendu : aucune métrique `9` rendue, `portal-read-result` = `UNKNOWN — contrat de lecture invalide`, token effacé, aucune valeur LIVE. Répéter avec `runtime_authenticated=true`, `live_remediation_authorized=true`, nombre négatif, `runs.items` de 101 éléments, `states.runs=UNKNOWN` avec objet non nul : **tous rejetés**.

Test de concurrence : déclencher réponse A lente, puis B ; résoudre B en 503, puis A en 200 avec enveloppe apparemment valide. Attendu : A ne réhydrate pas le DOM après B ; statut reste UNKNOWN. Test clear : effacer pendant A, puis résoudre A ; aucune donnée réintroduite. Vérifier `cache=no-store`, `credentials=omit`, `redirect=error` et absence de persistance du jeton. Un 200 sans preuve ne doit jamais devenir une attestation LIVE.

Critère positif **uniquement synthétique** : enveloppe explicitement qualifiée avec identité serveur, ACL tenant et états `READABLE_UNVERIFIED`, sans prétendre prouver un backend réel. Ne jamais fabriquer cette qualification côté navigateur ou contourner les contrôles tenant/HITL.

## Qualification et handoff
À renseigner séparément pour chaque cible : SHA de source, digest image complet, lien image↔source vérifié, horodatage UTC et TTL du reçu, méthode/route, statut HTTP, empreinte de réponse expurgée, acteur/tenant autorisé, résultat de test et CI **au SHA exact**. Sans ces éléments, ne déclarer ni régression ni restauration validée. Protocole rédigé, **non exécuté**. Pas de changement runtime, Docker, cinq stacks, cron, secrets, PostgreSQL/GLPI, `main`, merge ou déploiement.

Rollback de cet incrément GitHub : fermer la Draft PR ou revert ce seul fichier sur sa branche ; aucun rollback effectif Debian. Handoff à #555 ; handover `docs/ops/HANDOVER-AIOPS2-CURRENT.md` lu sur `docs/debian-deployment-qualification-plan-20261110` (absent de `main`), laissé intact pour éviter une collision documentaire.
