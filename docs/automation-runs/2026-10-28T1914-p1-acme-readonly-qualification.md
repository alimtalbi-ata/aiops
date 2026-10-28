# 2026-10-28 19:14–19:20 Europe/Paris — Owner E2E/Evidence, ACME read-only

## Point de départ et concurrence
- HEAD `main` vérifié avant modification : `793a5a03688dcb7c1a689d07e31bea770da4bd4f` (PR #136 fusionnée, Chromium éphémère).
- PR ouvertes examinées : #139 (NOC, dépend de #133), #137 (HITL projection), #133 (contrat scénario), #128 (timeline Evidence, conflit), #127 (60 CI, conflit), #121 (chaîne Evidence Studio). #133/#139 ne sont pas sur `main`; ne pas mélanger leurs IDs `SIM-EVT-ACME-*` avec des preuves runtime.
- Sources consultées : `docs/PROJECT-CONTINUITY.md`, `docs/QUALIFICATION-AND-CHANGE-PROTOCOL.md`, `docs/automation-runs/2026-10-28T1755-p1-explore-story-chromium-e2e.md`, `app/portal/acme_impact_read_model.py`, `app/portal/acme_explore_story.py`, `.github/workflows/quality.yml`.
- Branche dédiée : `fix/p1-acme-readonly-qualification-20261028-1914`, PR draft [#141](https://github.com/alimtalbi-ata/aiops/pull/141) vers `main`.

## Livraison verticale
- `scripts/qualify_acme_readonly.py` : script stdlib limité à `http://127.0.0.1:<port>`, refus des redirections et des URLs externes, lecture JSON bornée, jeton viewer par variable d'environnement non affichée. Appelle uniquement GET `/api/demo/acme-impact` et POST **stateless/read-only** `/api/demo/explore-story/control` ; vérifie 401 sans auth avant la lecture.
- Vérifie les deux projections réelles du portail local : SHA-256 source, Run **fictif** dérivé, incidents SAN P1/Payments P2, chemin du fixture, neuf checkpoints `MISSING`, absence de tickets/captures/horodatages attestés, Policy `DENY_LIVE_ACTION` et drapeaux de non-exécution.
- `tests/test_explore_story_playwright_e2e.py` : exécution de la recette contre le **vrai serveur FastAPI éphémère** existant, cas sans jeton, jeton invalide, faux IDs, faux LIVE, fausses preuves, fausse décision Policy, URL Debian/port malformé. Le workflow `quality.yml` existant exécute déjà ce fichier : aucun workflow parallèle ajouté.
- Nouveau contrat de sortie **additif** `aiops.acme-readonly-qualification.v1` : `contract_status=PASS` concerne exclusivement la cohérence des projections synthétiques ; `overall=NO_GO` reste obligatoire pour le parcours métier complet. Aucun endpoint existant modifié.

## Commits / CI
- Code : `d2d923ec8d146b29c0ed0f59c6d90d38a81cb9cc`.
- Tests : `80b7cf363ef587f2f361c93c1f2284bb042b1e0d`.
- Sécurisation diagnostics URL/jeton : `69ef945d0a08c222ab87a5522769e20ec812f3f6`.
- Tests négatifs additionnels : `af7378259d7ad31addcdb37adca82f4a2a18ed3e`, correction d'escape : `ae65dc0b9da93131e17d36d276a63063c5554370`.
- CI GitHub Actions `quality.yml` : [push #40743527482](https://github.com/alimtalbi-ata/aiops/actions/runs/40743527482), [PR #40743562450](https://github.com/alimtalbi-ata/aiops/actions/runs/40743562450) observés `in_progress` sur SHA antérieur `80b7cf3` ; **ne qualifient pas le HEAD final**. Résultat final à recontrôler sur SHA exact du journal. Tests locaux : **NOT_TESTED** (environnement local sans accès réseau GitHub). Aucun PASS revendiqué ici sans logs finaux.

## Matrice GO/NO-GO
| Contrôle | État |
| --- | --- |
| Cohérence du contrat Impact ↔ Explore/Story | CI HEAD final PENDING ; recette ajoutée |
| 401 anonyme, jeton viewer, fail-closed | CI HEAD final PENDING |
| Chromium ↔ FastAPI éphémère | CI HEAD final PENDING ; test existant réutilisé |
| Core → Temporal → Analyst/Critic → Policy → Evidence | NOT_TESTED |
| Corrélation vrai `run_id`/`incident_id`/`evidence_ids` | NOT_TESTED ; IDs actuels synthétiques |
| GLPI, n8n, Grafana, Thruk / métriques réelles | NOT_TESTED |
| Isolation tenant/RBAC runtime | NOT_TESTED |
| Captures opérateur authentifiées, confidentialité, vidéo client | NOT_TESTED |
| GO démo E2E métier | **NO_GO** |

## Risques, blocages et suite
1. **P0** : absence de liaison Core/Temporal/Policy/Evidence attestée ; ne pas promouvoir les références du fixture en preuve.
2. **P0** : les vraies captures et les métriques Payments ne sont pas qualifiées ; aucun récit de rétablissement réel.
3. **P1** : contrats #133/#139 et #128 non intégrés à `main` ; réconcilier par mapping explicite et tests, pas par fusion massive.
4. Prochain micro-lot : faire consommer la projection canonique #133 par la recette après intégration vérifiée, et exiger un reçu Evidence indépendant lié aux mêmes IDs, sans assumer `evidence_ids` fictifs.
5. Aucune requête à Debian, aucun déploiement, aucun secret, aucun effet LIVE ; aucun merge.

## Clôture de qualification GitHub (19:19 Europe/Paris)
- HEAD code + journal `4ca09a2b445888ae4a77d106b6606c7ba191742f` : [quality PR #40743738491](https://github.com/alimtalbi-ata/aiops/actions/runs/40743738491) et [quality push #40743727713](https://github.com/alimtalbi-ata/aiops/actions/runs/40743727713) : **completed/success**, trois jobs chacun. Logs du job `policy-and-static` vérifiés : **5 tests Playwright/portail** exécutés, dont la recette agrégée et les mutations négatives ; `Ran 5 tests in 3.325s`, `OK`. Tests Core/PostgreSQL et Grafana sur services éphémères : jobs SUCCESS, **sans** qualification du parcours ACME inter-services.
- Échec intermédiaire [#40743651602](https://github.com/alimtalbi-ata/aiops/actions/runs/40743651602) : assertion `invalid_viewer_token` non satisfaite, car le test passait un backslash littéral plutôt qu'un saut de ligne. Corrigé dans `ae65dc0` et revérifié sur HEAD final ; ne pas masquer cet échec.
- La présente clôture documentaire crée un nouveau commit : ses propres checks devront être vérifiés sur le SHA mis à jour avant fusion. Le code testé et les contrats ne changent pas.
