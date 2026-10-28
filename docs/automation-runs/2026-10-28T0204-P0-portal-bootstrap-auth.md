# Automation run — P0 Portail Core/Twin read gate

**Date:** 2026-10-28. **Début:** 02:04 Europe/Paris (01:04 UTC). **Périmètre:** GitHub source/CI uniquement. **Main HEAD au départ:** `0603e86a26978873c3b6196098674932d3378499` (vérifié via GitHub). **Branche:** `feat/p0-portal-bootstrap-read-auth-20261028-0204`. **PR draft:** [#74](https://github.com/alimtalbi-ata/aiops/pull/74), ouverte, non fusionnée.

## Lectures et décision

- Lu `main`, `docs/PROJECT-CONTINUITY.md`, `docs/QUALIFICATION-AND-CHANGE-PROTOCOL.md`, la roadmap de PR #39, les métadonnées des PR #36/#37/#39/#41/#43, et les PR concurrentes #51/#57/#70.
- Portage **ciblé** du contrat Bearer de bootstrap de PR #36 (`_require_portal_read_auth`), sans reprendre sa grosse branche divergente ni ses workers concurrents. Le registre `platform_registry` et le NOC signé sont déjà dans main; aucun remplacement.
- P0: les données Core/Twin étaient servies à l'anonyme via `GET /` et `GET /api/portal/bootstrap`. Cette PR rend le premier un shell UNKNOWN sans appel Core/Twin, et protège le second par un jeton lecture dédié, fail-closed.

## Fichiers

- `app/portal/main.py` : protection bootstrap, shell public sans upstream, endpoint JS local, widget lecture.
- `app/portal/portal_bootstrap_guard.py` : refus 401/503 non-cacheable et comparaison constante.
- `app/portal/portal_bootstrap_client.js` : token one-shot, rendu textContent, réponses tardives ignorées.
- `tests/test_portal_bootstrap_auth.py` : HTTP négatif et régression (6 tests, TestClient in-process).
- `tests/test_portal_bootstrap_client.mjs` : comportement navigateur synthétique (3 tests Node).
- `.github/workflows/quality.yml` : étapes Python/Node ajoutées au workflow existant.
- `docs/portal/BOOTSTRAP-READ-AUTH-P0.md` et `docs/PROJECT-CONTINUITY.md` : contrat, limites et handover.
- Ce journal.

## Commits

`ce91ca3`, `a6331f1`, `ae62ae2`, `3141453`, `c2dc10a`, `3a30ec8`, `916ee06`, `ee5239b`, `4ca1523`, `60d8736`; **SHA du dernier commit de code/tests/CI validé** `60d873661246fe214d58d33d2282cbe27270286a`. Le présent journal ajoute un commit documentaire ultérieur.

## Tests exécutés et résultats

**GitHub Actions** : [run 40613116675](https://github.com/alimtalbi-ata/aiops/actions/runs/40613116675) sur `60d873661246fe214d58d33d2282cbe27270286a`, **completed/success**, job `policy-and-static` **completed/success**. Étapes **success** : compilation Python, policy safety, intégrations/navigation, read models Core/Twin, nouveaux tests HTTP bootstrap, nouveaux tests Node du client, NOC signé/corrélation/RAG DEMO, impact ACME, preflight secrets, audit statique, `docker compose config` avec secrets CI générés. Aucun test réel Core/Twin en conteneurs ni E2E n'a été exécuté par cette PR; TestClient et DOM synthétique sont des tests unitaires/contractuels, pas des intégrations.

Le run ci-dessus valide le commit de code `60d8736`. Le commit documentaire final peut déclencher une autre CI : **ne pas extrapoler** ce résultat à un run non encore confirmé.

## Risques et blocages

- `/api/portal/components` et les liens configurés restent publics; `POST /api/demo` et `POST /api/copilot` sont traités séparément dans les PR draft #57/#70. Auth globale, SSO, RBAC par tenant et ACL Core ne sont pas encore qualifiés.
- Le lecteur HTTP Core/Twin existant utilise encore son timeout/retry historique; pas de qualification de latence ni de charge. L'interface exige un nouveau token pour chaque lecture, volontairement non persisté.
- LLM NGX/Mistral 192B, Ollama CI, vrais services éphémères, Debian 10.79.94.202, portail 17777, captures LIVE et vidéo finale : **NOT_TESTED** dans ce lot. Aucune preuve LIVE revendiquée. Aucun merge, deploy, migration, accès Debian ou remédiation LIVE.

## Prochain micro-lot

Réconcilier sur main, par portages ciblés, les PR #51 (Incident/Run/Evidence), #57 (DEMO) et #70 (Copilot) avec ce read gate; assurer que toutes les routes exposant des données ou effets ont un contrôle d'accès cohérent. Ajouter des tests de non-fuite entre rôles et une vraie intégration Core/Twin éphémère avant toute qualification runtime.
