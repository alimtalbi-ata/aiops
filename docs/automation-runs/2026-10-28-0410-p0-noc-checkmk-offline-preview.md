# Journal P0 NOC — 2026-10-28 04:10 Europe/Paris

## Contexte et périmètre

- Dépôt : `alimtalbi-ata/aiops`, base `main` vérifiée par compare : `1ed749129e32ea9a8854c437c7de9a6a8b43e35b`.
- PR examinées avant modification : #36, #37, #39, #41, #43 ; branches NOC concurrentes #71, #75, #78 inspectées, non écrasées.
- Documents lus : `README.md`, `docs/PROJECT-CONTINUITY.md`, `docs/ARCHITECTURE-AND-BOUNDARIES.md`, `docs/COMPONENT-CATALOG-AND-REUSE.md`, `docs/DECISION-LOG.md`, `docs/QUALIFICATION-AND-CHANGE-PROTOCOL.md`, roadmap de PR #39 `docs/DEVELOPMENT-ROADMAP-2026-10-27.md` (absente de main).
- Branche dédiée : `feat/noc-livestatus-offline-preview-20261028-0410`, PR draft [#83](https://github.com/alimtalbi-ata/aiops/pull/83). **Pas de merge, pas de déploiement, pas de LIVE**.

## Livraison

Portage ciblé PR #36 des règles de mapping/fraîcheur/colonnes Checkmk/Livestatus, sans import massif ni accès réseau. Nouveau `POST /api/noc/checkmk-export/preview` authentifié, hors ligne et non persistant, retour de compteurs d'états uniquement, jamais de noms d'hôtes ni plugin output. Panneau portail avec exemple **synthétique** explicite, et prévisualisation. Absence d'ACL tenant qualifiée, observation réelle et diagnostic IA marquée comme telle.

Fichiers : `app/portal/noc_checkmk_export.py`, `app/portal/main.py`, `tests/test_noc_checkmk_offline_preview.py`, `.github/workflows/quality.yml`, `docs/architecture/NOC-CHECKMK-OFFLINE-EXPORT-PREVIEW-20261028.md`, `docs/PROJECT-CONTINUITY.md`, présent journal.

Commits de code/tests/CI/docs :
- `7d42074e299619626aba9a0f4702d94b757ebdfc` : adaptateur de prévisualisation ;
- `45a1d3a7923374fd7c61deea945028f0331eb5c7` : intégration UI portail ;
- `97ed500ae56fd6eaafde632790a626c9b317ec67` : tests négatifs et non-régression ;
- `b810d078c51f1ce089b3a7119454fbec09254498` : step de test dans CI existante ;
- `3cfe81aba1d64ae028cadd00f8ffe4965348f73f` : architecture et limites ;
- `08ac84065f2d8af672b1dcb1c2ea1bbbf9240742` : continuité.

## Validation exécutée

- [GitHub Actions quality.yml run 40625305468](https://github.com/alimtalbi-ata/aiops/actions/runs/40625305468) sur commit `b810d078c51f1ce089b3a7119454fbec09254498` : **completed/success** confirmé. Job `policy-and-static` **success**, y compris `Offline Checkmk export preview security and regression tests`, compilation Python, tests NOC antérieurs, tests sécurité, audit statique, validation Compose. Résultat réellement vérifié via liste des jobs/steps.
- Runs documentaires suivants : [40625328400](https://github.com/alimtalbi-ata/aiops/actions/runs/40625328400) et [40625339504](https://github.com/alimtalbi-ata/aiops/actions/runs/40625339504) : **in_progress au moment de la rédaction**, ne pas les annoncer PASS sans nouvelle vérification.
- Tests locaux isolés : **NOT_EXECUTED**, dépôt non accessible par réseau depuis l'environnement d'exécution ; le test contractuel a été exécuté dans GitHub Actions.
- Checkmk/Thruk conteneur réel, Grafana métriques, Core ACL multitenant, NIM/NGX, E2E Debian : **NOT_TESTED/BLOCKED**. Aucun substitut Checkmk présenté comme test d'intégration.

## Risques, blocages, retour arrière et suite

- Le jeton opérateur est partagé et non tenant-scoped : la réponse n'expose que des agrégats ; toute extension nominative nécessite ACL Core et identité tenant.
- La date `captured_at` est déclarative, non authentifiée ; fraîcheur ne prouve ni provenance ni observation.
- Aucun fournisseur Checkmk/Thruk CI authentifié ni service qualifié ; le POST ne prouve qu'un parseur de contrat.
- Rollback source : revert de la PR #83, aucun schéma ni état persistant à migrer.
- Prochain micro-lot : démarrer un vrai Checkmk éphémère en CI, qualifier un export GET read-only avec credentials de test, établir une provenance signée et une ACL tenant avant corrélation Run et observabilité Grafana. Conserver `CI_SIMULATED_LLM` uniquement pour l'endpoint NGX lorsque le contrat LLM sera testé.

## Vérifications complémentaires et correction UI

- [GitHub Actions 40625339504](https://github.com/alimtalbi-ata/aiops/actions/runs/40625339504) sur `08ac84065f2d8af672b1dcb1c2ea1bbbf9240742` : **completed/success** confirmé après rédaction initiale.
- [GitHub Actions 40625380846](https://github.com/alimtalbi-ata/aiops/actions/runs/40625380846) sur `61c27f92759dd754d8e9d03075ea7330c6943b3f` : **completed/success** confirmé, journal initial inclus.
- Relecture du HTML : correction de la génération de l'horodatage de l'exemple synthétique avec `toISOString().slice(0,19)+'Z'`, commit `06c6aa20d8a6290e8f84a6601a347f9ad85e80bd`. Ce correctif doit repasser la CI ; ne pas attribuer les résultats antérieurs au nouveau HEAD.
