# Agent 5 — reproduction indépendante de la candidate #462

Date du rapport : 2026-11-09T21:18:58.697399+00:00 (UTC).
SHA effectivement exécuté : `3f2e361c1997ff14a490bb240eea902820a1302f`.
Branche de référence : `agent/integration/462-isolated-candidate`.
Clone indépendant propre, HEAD détaché : `/workspace/agent5-repro-462`.
Branche Twin #460 préservée dans `/workspace/aiops` au SHA `a555f2be5ba5a204caee674b4dfeadbf27256e77`.
Aucun fichier source, test, migration ou harness modifié. Aucun merge, déploiement Debian ou accès production.

## Commandes exécutées

```bash
git clone --no-hardlinks /workspace/aiops /workspace/agent5-repro-462
git -C /workspace/agent5-repro-462 checkout --detach 3f2e361c1997ff14a490bb240eea902820a1302f
cd /workspace/agent5-repro-462
python3 tools/qualification/bench462.py --root /workspace/agent5-bench-462
```

Commande du harness : exit 0. Sortie intégrale : `bench-command.log`.
Avant exécution : Docker local 29.9.2, neuf nouveaux conteneurs sur un réseau interne, aucun conteneur existant observé sur ce daemon. Aucune connexion à un daemon distant.
Image construite depuis les sources exportées par git archive au HEAD exact. Projet aléatoire `aiops2-agent7-462-dad67c67` ; le préfixe/label Agent 7 est hérité du harness inchangé et ne désigne pas le banc précédent. Racine Agent 5 distincte.

Pour les tests : copie exacte des cinq fichiers vers `/qualification/tests` dans le Core du nouveau banc, migrations d'origine vers `/qualification/db`, lien `/qualification/app -> /app`. Ainsi `/app` conserve le manifeste applicatif vérifié. Aucun montage production ni changement de configuration d'un autre projet. Commande reproductrice complète : `python3 /workspace/agent5-repro-evidence/run-unit-tests.py` (exit 0).
Chaque suite est exécutée dans un processus séparé :

```bash
docker --host=unix:///var/run/docker.sock exec -w /qualification <nouveau-core-id>   python -m unittest discover -s tests -p '<fichier-ci-dessous>' -v
```

| Suite | Tests | Résultat |
| --- | ---: | --- |
| test_hitl_identity.py | 11 | PASS |
| test_hitl_workflow_contract.py | 9 | PASS |
| test_intelligence_contract.py | 16 | PASS |
| test_critic_schema_retry_v24.py | 4 | PASS |
| test_candidate_core_execute.py | 7 | PASS |
| Total | 47 | PASS, aucune erreur/échec/skip |

Les IDs de conteneur, commandes exactes, timestamps et codes de sortie figurent dans `unit-test-results.json`, les sorties dans `unit-*.log`. Python : `Python 3.13.18`. Dépendances réellement installées : `pip-freeze.txt`.
Les fixtures de migration ont été fournies avant les tests : aucune reproduction de l'erreur initiale de chemin absente dans le premier essai Agent 7, aucune modification de test/xfail.

## Nouveau Run et preuves fonctionnelles

- Run : `RUN-57EE6BF058F80903` (différent du Run publié).
- Incident : `INC-BENCH462-B387913B1D81`.
- Temporal Run ID : `01a1c222-b09b-7b88-8aa5-c222f14551df`.
- Core RESOLVED ; Temporal COMPLETED ; INGEST et 13 stages PASS.
- Policy PASS/SIMULATE ; un registre Analyst, un registre Critic validé, un registre Policy.
- Replay SDK du nouvel historique : PASS ; 95 événements.
- Trois appels execute supplémentaires : reçu idempotent identique, une seule ligne durable, même Temporal Run ID, historique inchangé 95→95.
- Dispatch Worker HTTP : 1 avant / 1 après les trois retries ; aucun second dispatch observé.
- HITL DEMO explicitement synthétique, execution_allowed=false ; zéro approbation et zéro ligne d'outbox ; identité humaine par token interne refusée HTTP 503.
- Stabilité mesurée par le harness : 95 secondes ; snapshot complémentaire horodaté `runtime.json` : neuf conteneurs running, sept healthchecks healthy, zéro restart, zéro port publié, réseau internal=true.

Preuves : `receipt.json`, `run.json`, `ledger.json`, `history.json`, `client-run.log`, `client-retry.log`, `services.log`, `runtime.json`.

## Comparaison et divergences

1. **Source applicative identique** : manifeste `49b98b4840c2db6a74318a773e1fbffe6062345507dc7f38b8f602c37c0bd8a3`, exactement celui de la preuve publiée. Comparaison #194 : 63/64 fichiers byte-identiques ; seul app/core/main.py diffère (`preservation.json`).
2. Nouveau projet, secrets aléatoires propres au banc, PostgreSQL jetable, nouveaux IDs Run/Incident/Temporal : séparation attendue et observée.
3. Image reconstruite : `sha256:845e8789c87741b28a98e18a27d94a65f6a67f5fafcd84a5a8b71bfd65b5a746` ; image Agent 7 publiée : `sha256:4d4720c1caa132ed62c98dc9133dfd8ecd6bc1abc6d6ebe1ae4e9bcfa74f1818`. Ce n'est **pas** une reproduction binaire du digest précédent. Source et comportement ciblé identiques ; base Python 3.13-slim et image PostgreSQL sont des tags flottants, dépendances transitives non gelées. Le digest différent ne permet pas à lui seul d'attribuer la cause exacte ; versions locales conservées.
4. Label de révision de la nouvelle image = SHA examiné `3f2e361c1997ff14a490bb240eea902820a1302f` ; ancienne image réutilisée labellisée `8fced982...`. Le reçu stable précédent avait source_commit `a4ea1970...` ; `git diff a4ea1970 3f2e361c1997ff14a490bb240eea902820a1302f -- app tools/qualification db/migrations` est vide.
5. Stabilité du harness : 95 secondes ici contre 98 précédemment ; mêmes résultats, 95 événements et aucun redispatch.
6. Les cinq suites passent dès leur première exécution ici, car les migrations d'origine sont présentes au chemin attendu. Pas de suppression de l'échec historique Agent 7.

Comparaison structurée : `comparison.json`.

## Complément e0fc66c3 — revue différentielle seulement

SHA complément : `e0fc66c3bc8f56cace0074de2f0a07d5bb551303`. Diff conservé dans `delta-e0fc66c3.patch`.
Quatre chemins modifiés : `.github/workflows/quality.yml` et trois documents sous `docs/handoffs/integration/qualification-462/`.
Application, tests, outils de banc et migrations : `git diff --exit-code 3f2e361c1997ff14a490bb240eea902820a1302f e0fc66c3bc8f56cace0074de2f0a07d5bb551303 -- app tests tools db` retourne 0.
Le workflow ajoute uniquement le trigger push de cette branche et une étape pour les sept tests Core déjà exécutés. Aucun job/permission/garde existant retiré. Les docs précisent l'ownership CI et la préparation de PR, sans changer le runtime.

**Conclusion de portée :** les conclusions locales des 47 tests et du Run DEMO restent applicables au contenu applicatif inchangé de `e0fc66c3bc8f56cace0074de2f0a07d5bb551303`. Le SHA effectivement exécuté reste `3f2e361c1997ff14a490bb240eea902820a1302f` ; aucune exécution de banc ni CI au nouveau SHA n'est revendiquée. Pas de relance complète nécessaire pour ce complément documentaire/CI. La nouvelle étape CI reste à observer sur GitHub ; un run de PR sur merge synthétique ne remplace pas la vérification du head_sha.

## Limites et conservation

PASS indépendant **DEMO Cloud isolé uniquement**. Fournisseur déterministe synthétique existant : ni modèle réel, ni GLPI authentifié, ni approbation OIDC réelle, ni navigateur qualifiés. Debian, FS1250 et E2E réel restent HOLD/NOT_VERIFIED. Cette validation ne corrige ni ne qualifie la régression Twin fixture:// de l'autre branche.
CI GitHub non revendiquée. Aucun nouveau PR, merge ou push sur les branches des autres agents. Livraison par branche Git dédiée `agent/twin/462-independent-validation` ; aucune publication de commentaire d’issue revendiquée. La branche Twin #460 et la candidate d’Intégration restent inchangées.
Banc laissé intact et actif, ressources limitées à son projet ; aucune suppression/nettoyage des autres ressources.
Empreintes : `SHA256SUMS`. Le compose privé contenant les secrets n'est pas inclus dans ce paquet ; inspection des preuves pour les secrets propres au banc effectuée.

## Livraison nocturne

Agent 5 termine cette mission après publication de ce dossier. Le CLI Debian reprend la coordination ; aucune nouvelle tâche, aucun merge ni déploiement engagé. Blocages restants : CI exacte non vérifiée ; GLPI/OIDC/modèle réel/navigateur non qualifiés ; Debian/FS1250/E2E réel HOLD ; divergence de digest de construction non attribuée précisément. Le défaut Twin fixture:// reste hors de cette validation. Aucun secret ni compose privé inclus.

Publication : seuls les espaces de fin de ligne du log services et du diff de revue sont normalisés ; empreintes avant/après dans `publication-normalization.json`, originaux locaux conservés. Le diff publié sert à la lecture, pas à une application automatique.
