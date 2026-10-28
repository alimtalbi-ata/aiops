# P0 — Core/Twin bootstrap convergence — 2026-10-28 10:04–10:07 Europe/Paris

## Point de départ
- Repository: `alimtalbi-ata/aiops`; `main` HEAD initial et recontrôlé `111b3bd5988ac35cd5f83c1fc93813b96c09111e`.
- PRs relues: #36, #37, #39, #41, #43, #74, #103. Documents lus: README, PROJECT-CONTINUITY, ARCHITECTURE-AND-BOUNDARIES, DECISION-LOG, COMPONENT-CATALOG-AND-REUSE, QUALIFICATION-AND-CHANGE-PROTOCOL, docs/portal. Aucun fichier ROADMAP nommé trouvé dans l'arbre main.
- Branche `fix/p0-portal-bootstrap-converge-20261028-1004`; [PR draft #114](https://github.com/alimtalbi-ata/aiops/pull/114). Commit code/tests/docs `5d503a86419e96209520ce369b8ded6b2a9b23c2`. Aucun commit sur main, aucune fusion.

## Fichiers
- `app/portal/main.py` : Bearer viewer obligatoire avant Core/Twin; page publique UNKNOWN sans appels upstream; route statique JS.
- `app/portal/portal_bootstrap_client.js` : portage ciblé de #74, contrôle d'enveloppe, affichage textuel, jeton éphémère, cookies omis, réponse tardive ignorée.
- `tests/test_portal_bootstrap_auth.py` et `tests/test_portal_bootstrap_client.mjs` : refus 401/503, aucun upstream sur refus, UNKNOWN sur erreur, faux LIVE/malformed, effacement, régression.
- `.github/workflows/quality.yml` : tests ajoutés au workflow existant, pas de CI parallèle.
- `docs/portal/BOOTSTRAP-CONVERGENCE-P0.md`, `docs/PROJECT-CONTINUITY.md`, `docs/DECISION-LOG.md` et ce journal.

## Exécutions vérifiées
- [Actions push 40661542576](https://github.com/alimtalbi-ata/aiops/actions/runs/40661542576) sur `5d503a86419e96209520ce369b8ded6b2a9b23c2` : `completed/success`, jobs `policy-and-static` et `grafana-real-integration` success.
- [Actions PR 40661558336](https://github.com/alimtalbi-ata/aiops/actions/runs/40661558336) sur le même SHA : `completed/success`, mêmes jobs success.
- Étapes réellement confirmées : compilation Python, tests HTTP bootstrap, tests Node DOM/syntaxe, navigation, Policy/NOC, audit statique, Compose config et Grafana réel en conteneur éphémère (HTTP health et adaptateur). Les tests bootstrap utilisent un upstream patché in-process : **pas** une intégration Core/Twin. Aucun test local, Ollama ni NGX exécuté. Le commit de ce journal requiert sa propre CI (non anticipée).
- Pas de capture authentifiée, vidéo ni preuve LIVE.

## Risques, blocages et suite
- Viewer Bearer partagé ≠ SSO/ACL tenant. États `READABLE_UNVERIFIED` / `UNKNOWN` non attestés. Intégrations réelles Core/Twin, n8n, Checkmk/Thruk, GLPI, navigateur, Ollama 4B et captures : `NOT_TESTED`/`BLOCKED`; seul Grafana réel a été vérifié dans CI.
- DEMO/Copilot restent publics dans main : converger #57/#70 avec refus avant appels backend. Puis allowlist #82 et ACL tenant. Ne pas fusionner sans checks du dernier HEAD et absence de conflits.
- Aucun accès Debian 10.79.94.202 ou portail 17777, aucun déploiement, aucune commande LIVE.

## Fusion et CI post-fusion — 2026-10-28 10:09 Europe/Paris
- PR [#114](https://github.com/alimtalbi-ata/aiops/pull/114) passée en review puis fusionnée par squash, SHA `cea1ed7b54ed34cf4b036b6d5f20bf968c9dac09` ; GitHub a confirmé `merged=true`. Avant fusion, base `111b3bd5988ac35cd5f83c1fc93813b96c09111e` inchangée, `mergeable_state=clean`, aucun conflit, quatre checks sur HEAD final `4b853894c523dacad4ffcb5ffc8007f1c164d0b7` terminés `success`.
- [CI push final 40661742307](https://github.com/alimtalbi-ata/aiops/actions/runs/40661742307) et [CI PR final 40661749480](https://github.com/alimtalbi-ata/aiops/actions/runs/40661749480) : `completed/success`, jobs policy/static et Grafana réel en conteneur `success`.
- [CI post-fusion main 40661890151](https://github.com/alimtalbi-ata/aiops/actions/runs/40661890151) : `completed/success`. Aucune preuve Core/Twin réelle, tenant ACL, navigateur ou LIVE n'est ajoutée par ces résultats.
- Le présent addendum est une mise à jour documentaire distincte; pas de modification du code applicatif.
