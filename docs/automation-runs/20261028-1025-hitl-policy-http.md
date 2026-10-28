# P0 HITL — API Policy fail-closed, 2026-10-28 10:25 Europe/Paris

## Base et vérifications
- Départ `main`: `bb4665ab0eb41b43df43ea893e28ac86ef640863` (HEAD lu avant modification). PR draft existante [#76](https://github.com/alimtalbi-ata/aiops/pull/76), HEAD initial `840eff93ff3d88dc0c301f1f34eea20e8c00fe02`; aucune réécriture de l'historique ni de `main`.
- Lectures: main, PR #36/#37/#39/#41/#43, PR #49/#72/#76/#106, `docs/PROJECT-CONTINUITY.md`, architecture, ADR, tests et `.github/workflows/quality.yml`.
- Réutilisation ciblée de PR #36: principe `execution_fence.py` « admission simulation ≠ permission d'effet LIVE » ; aucun portage massif de `autonomy_store` ni nouveau service.
- La PR #76 contient déjà le verrou deny-only de `app/policy/main.py` pour LIVE `EXECUTE/RESOLVE/REMEDIATE/CANCEL`, malgré `human_approved=true`. Le `main` observé conserve le bypass booléen tant que cette PR n'est pas fusionnée.

## Micro-lot et commits
- `tests/test_policy_safety.py`: trois tests négatifs et de non-régression sur l'API FastAPI réelle **en processus**: quatre commandes LIVE avec booléen forgé, modes/commandes invalides (HTTP 422), DEMO/REPLAY/STORY toujours SIMULATE. Pas de mock présenté comme test d'intégration.
- Commit code/tests: [`e5b7cba894d5b6140703322df97f47b0dd7caaf1`](https://github.com/alimtalbi-ata/aiops/commit/e5b7cba894d5b6140703322df97f47b0dd7caaf1).
- Ce journal est un commit documentaire séparé sur la même PR ; consulter le HEAD GitHub pour son SHA final. Pas de commit vide.
- Fichiers modifiés dans ce micro-lot: `tests/test_policy_safety.py` et ce journal. Les autres fichiers de PR #76 sont antérieurs à cette exécution.

## Validation honnête
- Ancien HEAD de PR #76: [GitHub Actions #40615101519](https://github.com/alimtalbi-ata/aiops/actions/runs/40615101519) terminé `success`, **ne couvre pas** les trois nouveaux tests.
- Nouveau HEAD: `quality.yml` existant doit exécuter `test_policy_safety.py`; **PENDING / NOT_TESTED** jusqu'à vérification du run, de son SHA et des jobs. Aucun test local exécuté dans ce micro-lot.
- Tests Core/Temporal/RBAC/Evidence, sandbox SQLite en conteneur, Ollama CI 4B, NGX 192B, E2E et Debian: **NOT_TESTED / BLOCKED**. Ce micro-lot n'utilise aucun LLM ni secret de production.

## Risques, rollback, prochain micro-lot
- PR #76 diverge de `main` (16 commits derrière au début). Ne pas fusionner sans recontrôler les checks sur le dernier HEAD, l'absence de conflit et l'effet sur `main`.
- L'API Policy n'authentifie pas de jeton HITL ; le booléen est insuffisant. La protection est deny-only, non une autorisation LIVE. Les tests HTTP restent in-process, pas une preuve de service conteneurisé.
- Rollback du test isolé possible par revert du commit de tests ; ne pas supprimer le verrou LIVE sans remplacement authentifié.
- Suite: vérifier Actions, puis intégrer la protection à `main` seulement si la CI et la fusion sont sûres ; converger la pile #49 → #106 avec Core Run canonique et identité RBAC vérifiée, conserver une approbation atomique expirante et les postchecks/rollback `NOT_EXECUTED` du lab.
- Aucune commande LIVE, aucun accès au serveur Debian ou au portail privé, aucun déploiement, aucune capture ou preuve LIVE.
