# 2026-10-29 18:20 CET — ACME 1/5 : localiser un run Payments existant sans injection

**READY_FOR_STABLE=BLOCKED ; DEMO_READY terrain=NOT_READY.** Issue #186 consultée. Aucun accès Debian, aucune écriture Core/DB, aucun LIVE, aucune promotion stable, aucun ticket GLPI créé.

## Livraison ciblée et source

Branche de handoff **feat/p0-acme-core-run-locator-20261029-1820**, créée depuis **prep/acme-demo-offline-20261029** au SHA `3fe1d322189c0c028037af28a38872ccb6fbbb93`. Commit code `bf3cd301be24b34b965d6cc993186e702c0657ed`, code + tests `4d18f53518c16caedcbe2ddd93f422db8d86fb15`.

- `tools/find_acme_demo_run.py` : trois lectures GET Core `/api/runs`, `/api/incidents?limit=500`, `/api/runs/{rid}`. Retourne un `run_id` seulement si Core confirme **mode DEMO/REPLAY/STORY**, scénario `SCN-GOLDEN-PAYMENT-P1`, incident lié, `synthetic=true`, service `ACME-SVC-PAYMENTS`, source `portal-demo`/`portal-demo-enriched`/`synthetic-simulator`, identité du détail cohérente. Sortie JSON avec liens `/demo-studio?run_id=...` et `/timeline?run_id=...`, types d'événements et **références Evidence non attestées**. Sinon `UNKNOWN` et exit 2. Pas d'injection ni effet.
- `tests/test_find_acme_demo_run.py` : 12 assertions hors réseau (match, refus LIVE, faux incident, non synthétique, mauvais service/scénario/source/ID, détail divergent, contrats absents, absence d'événements).
- Les arêtes topologiques sont **ACME-E08/E06/E04/E02/E01**, `db/migrations/005_seed_acme.sql`, dépendances consumer→dependency, traversée inverse depuis `ACME-SAN-FABRIC-A`. Ce sont des **hypothèses de dépendance seedées**, jamais une panne Payments runtime attestée.
- Le scénario `SCN-GOLDEN-PAYMENT-P1` est seedé avec `INCIDENT_OPEN` sur `ACME-SVC-PAYMENTS` puis `SET_STATE` sur `ACME-SAN-FABRIC-A`. L'API Simulator `POST /api/launch` existe et refuse LIVE ; **non appelée** pour éviter toute écriture non approuvée.
- Run historique `RUN-A4449145A6E377FF` cité dans `docs/ACME-DEMO-RUNBOOK-V2114.md` : son appartenance au scénario SAN/Payments **n'est pas démontrée**. `RUN-ACME-OFFLINE-001` est une fixture, **pas** un run Core.

## Tests exécutés

`python3 -m unittest discover -s tests -p test_find_acme_demo_run.py -v` : **12/12 PASS**, Python local éphémère, pas Debian. `python3 -m py_compile tools/find_acme_demo_run.py tests/test_find_acme_demo_run.py` : PASS. Les deux fichiers GitHub ont les mêmes Git blob SHA que les fichiers locaux testés : script `c53060088237ce2dfd05034bc1b39431b75cbcc6`, tests `6d79d8d1b8e38dd588650ebef4ef4656e653266c`.

**CI quality.yml sur cette branche : NOT_RUN** (pas de PR ajoutée). Candidate intégrée existante #185, SHA lu `6eb5b23e55c72c827a433e2c5788b501ebdaaf4f`, workflow quality.yml `40920071906` SUCCESS, **sans ce nouveau script**. Ne pas confondre ces checks.

## Commande opérateur de vérification minimale (lecture seule)

Depuis un checkout isolé de cette branche, dans un environnement où Core est joignable en lecture, **sans toucher au worktree historique contenant demo_v2.py non suivi** :

```bash
python3 tools/find_acme_demo_run.py --core-url http://127.0.0.1:810 --portal-url http://127.0.0.1:7777
```

Sortie attendue : `SOURCE_VERIFIED_REGISTRY_ONLY` avec `run_id` et URL si Core expose un enregistrement admissible ; sinon `UNKNOWN` et exit 2. **Aucune sortie terrain obtenue**. Le Core de ce code expose des GET non authentifiés : cette commande ne constitue ni RBAC tenant ni preuve d'attestation. Utiliser uniquement une interface locale autorisée et ne pas publier de dump d'incidents.

## Contrats, limites et coordination

`SOURCE_VERIFIED_REGISTRY_ONLY` signifie concordance des registres Core consultés, **pas** causalité SAN→Payments, validation IA, approbation HITL, ticket GLPI, attestation Evidence, effet ou E2E. `payments_runtime_impact=UNKNOWN`, `tenant_acl_qualified=false`, `e2e_attested=false` sont explicites. Aucun contrat API existant modifié ; aucun module Portal/ITSM/Policy touché. Le script ne prouve pas la disponibilité de Core et ne contourne aucune authentification.

**NOT_TESTED :** Core HTTP réel, run_id observé sur Debian, Evidence/Analyst/Critic/Policy corrélés, tenant A/B, `applied.sha`, rollback, smoke terrain et déploiement. `main=27deb9b1a66faf27df8d69b137a63451f7649d80` ; stable `e54c4e9a9b37e6229559a1b587c9a06b4741a8b3`.

**Handoff à Recette 5/5 :** reprendre les deux fichiers sur la candidate unique #185 uniquement si utile à la présentation ; exécuter la commande read-only sur un Core autorisé, transmettre le `run_id` observé et les liens au responsable Portal, puis requalifier le SHA intégré en CI. Ne pas pousser stable depuis 1/5. Le cron 5 min ne suit que stable, pas cette branche.
