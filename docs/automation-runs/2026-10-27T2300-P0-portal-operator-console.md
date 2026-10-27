# 2026-10-27 23:00 CET — P0 Portail opérateur, lecture seule

## Départ / périmètre
- Heure locale : 2026-10-27 23:00 CET (Europe/Paris).
- `main` vérifié par GitHub commit API : `b85383f201c976397a512c9beb31857ddf7c1638`.
- PR #51, branche `feat/portal-operator-read-rbac-20261027-2155`, HEAD initial vérifié : `9bad78d7f665b4aaed0d246917c0665c8069c114`.
- Lecture : main, PR ouvertes #36/#37/#39/#41/#43 et #51, README, continuité, architecture, décisions, qualification, registre PR #36 et API RBAC PR #51. Pas de fusion massive PR #36.

## Livrables / commits
- `app/portal/operator_console.py` — `cb47596707600161dbd992835d3dc0ada0352b48` : page HTML lecture seule, headers CSP/no-store/anti-framing, JS même origine.
- `app/portal/operator_console.js` — `fa884cca3d2fc3a9d15c0b76bcc86e08347c715f`, correction `66d9dba29c5d8d968ef2d79f1c7a3a4e6b701f11` : jeton mémoire, états UNKNOWN, liste de champs autorisés, clôture des réponses asynchrones après déconnexion.
- `app/portal/main.py` — `a7aef540452718e18bbc752bb40266078fa6f224` : montage de la page et lien depuis le portail canonique.
- `tests/test_portal_operator_console.py` — `1c08dd5ce304e314a98a7c8fa930b3d40c232d6d` : routes, headers, sécurité statique, RBAC non contourné.
- `tests/test_portal_operator_console.mjs` — `db8fde4a0331868b83114400d22a49eb46147249` : JS exécuté sous Node, rendu textuel, jeton, 401, réponse tardive, provenance invalide.
- `.github/workflows/quality.yml` — `c269fe2686884b4704afa0f2734066dc2c1ae153`, `ef1c9d93b6dbdf5ee2d97ca1a9ef70fd13b605aa` : réutilisation du workflow qualité existant, tests Python et Node 22.
- `docs/portal/OPERATOR-READ-RBAC-P0.md` — `bacaa99f4e28ea5b58150d7e3b11638b5a10ce7d`; continuité `8584ab76f346b10cbd19960cfba24ac04a47e756`; ADR `c428fcb1cd16337d13ba61570f518a4916fd6447`.

## Tests réellement exécutés
- GitHub Actions `quality.yml` : **SUCCESS** pour le commit `ef1c9d93b6dbdf5ee2d97ca1a9ef70fd13b605aa`, [run 40591730091](https://github.com/alimtalbi-ata/aiops/actions/runs/40591730091). Job `policy-and-static` confirmé SUCCESS, étapes : compilation Python, policy, registry/navigation, Core/Twin, NOC signé, ACME, Core incidents, API operator RBAC, nouvelle console HTTP, **Node JS behavior and negative tests**, secret preflight, static audit et `docker compose config` toutes SUCCESS.
- Ancien commit `c269fe2686884b4704afa0f2734066dc2c1ae153` : [run 40591622931](https://github.com/alimtalbi-ata/aiops/actions/runs/40591622931), SUCCESS.
- Au moment du journal, HEAD documentaire `c428fcb1cd16337d13ba61570f518a4916fd6447` : [run 40591794979](https://github.com/alimtalbi-ata/aiops/actions/runs/40591794979), **IN_PROGRESS**, ne pas déclarer PASS pour ce SHA sans vérification ultérieure.
- `NOT_TESTED` : navigateur réel Playwright, intégration Core/PostgreSQL + Evidence/PostgreSQL, Thruk/Checkmk, Grafana, n8n, GLPI, Debian et portail 17777; aucune capture LIVE. Node utilise un DOM de test en mémoire : test unitaire de code JS, **pas** simulation d'un service intégration.

## Risques / limites / prochain micro-lot
- Le shell `/operator` ne renvoie aucune donnée sans Bearer; l'API applique le RBAC. Le reste du portail (`/`, `/api/demo`, `/api/copilot`) reste hors du périmètre d'authentification globale. Le jeton saisi en mémoire nécessite HTTPS et un navigateur de confiance.
- `READABLE_UNVERIFIED` n'est pas une attestation LIVE; le rôle viewer n'obtient pas Evidence. Aucune remédiation, aucun appel NGX/NIM, aucune fusion ni déploiement.
- PR : [#51](https://github.com/alimtalbi-ata/aiops/pull/51) — draft, poursuivre la qualification du dernier SHA. Prochain lot : auth globale/session/CSRF pour les routes historiques et CI d'intégration Core/Evidence en vrais conteneurs éphémères, sans mocks présentés comme service réel.
