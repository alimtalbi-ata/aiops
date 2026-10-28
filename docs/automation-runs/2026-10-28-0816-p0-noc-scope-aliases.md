# P0 NOC — aliases de portée tenant (2026-10-28 08:16 Europe/Paris)

- **Départ main vérifié :** `aae50b02557143ea5a7f0f2633271a0602de8800` (fusion PR #99).
- **Branche dédiée :** `fix/noc-scope-aliases-20261028-0816` ; aucune modification des branches des autres créneaux.
- **Lecture préalable :** main, PR ouvertes #36/#37/#39/#41/#43, PR #58/#71/#75/#78/#83/#88/#99, README, continuité, architecture, décisions, catalogue, protocole de qualification, `quality.yml`.
- **Réutilisation :** scanner du read-model signé de PR #99 (issu du contrat NOC PR #36), étendu de façon ciblée ; aucun merge massif.
- **Fichiers :** `app/portal/noc_runtime.py`, `tests/test_noc_tenant_scope_fence.py`, `docs/PROJECT-CONTINUITY.md`, ce journal.
- **Changement :** refuse les aliases de portée tenant indirects, y compris sous `extra.metadata`, même avec HMAC valide ; préserve les champs non scopés et le refus 503/no-store. Ne constitue pas une ACL.
- **Tests :** `quality.yml` existant lance `test_noc_tenant_scope_fence.py`, la compilation, les régressions NOC et les contrôles statiques. Résultats en attente de l'exécution GitHub Actions sur le HEAD de cette branche ; aucune intégration réelle Checkmk/Thruk/Core tenant/Grafana/Ollama n'est revendiquée.
- **Commit/PR :** à compléter après création et CI.
- **Risques :** rejet conservateur de champs ambigus, aucune identité tenant authentifiée, aucune isolation multitenant Core qualifiée.
- **Blocages :** tests A/B avec vrai Core/Postgres et fournisseur Checkmk/Thruk réel = NOT_TESTED/BLOCKED ; aucune capture ni preuve LIVE.
- **Prochain micro-lot :** authentification tenant Core et tests d'isolation A/B avec service réel éphémère ; puis métriques Grafana et RAG sourcé.
- **Sécurité :** aucun accès Debian 10.79.94.202, aucune commande LIVE, aucun déploiement, aucune migration ni appel NGX.

## GitHub — exécution vérifiée 2026-10-28 08:18 Europe/Paris

- **PR draft :** [#104](https://github.com/alimtalbi-ata/aiops/pull/104).
- **Commit code/tests/docs :** `b4cc72da867acc9a4e333b0ffa8cfbd6a594ceeb` (4 fichiers, aucune écriture sur main).
- **GitHub Actions :** [quality.yml run 40649223851](https://github.com/alimtalbi-ata/aiops/actions/runs/40649223851), HEAD `b4cc72da`, **completed/success**. Job `policy-and-static` : compilation, tests sécurité NOC existants et nouveaux (dont aliases et non-régression), corrélation, RAG, tests policy/portal, preflight secrets, audit statique et validation Compose = success. Ce sont des tests unitaires/contractuels, pas des services intégrés.
- **Fusion précédente PR #99 :** [PR #99](https://github.com/alimtalbi-ata/aiops/pull/99), squash SHA `aae50b02557143ea5a7f0f2633271a0602de8800`, CI avant fusion [40642379077](https://github.com/alimtalbi-ata/aiops/actions/runs/40642379077) completed/success, mergeable clean avant fusion.
- **État de la présente PR :** brouillon, non fusionnée au moment de cette entrée. Le commit documentaire de mise à jour déclenche un nouveau check : ne pas réutiliser le statut du commit précédent pour prétendre qualifier le HEAD final.
