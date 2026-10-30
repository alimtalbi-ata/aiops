# 2/5 — Portail P0, disponibilité des sources et navigation Core (2026-10-29 23:49 UTC)

Branche : `feat/p0-portal-source-status-20261030-0049`. Parent : `da778efc3c941e1801871e9d2b30927a4c9953ac` (PR #185). Ce commit reste **hors stable** et doit être repris uniquement par 5/5 après qualification.

## Changement borné
- `app/portal/main.py` : conserve le code HTTP 401/403 dans la réponse UI d'erreur, sans URL ni jeton ; affiche CONNECTED uniquement si le schéma de réponse API est minimalement cohérent, UNAUTHORIZED/UNAVAILABLE sur erreurs explicites, UNKNOWN sinon. NOT_INSTALLED n'est jamais déduit d'un HTTP 404 ou de l'absence de GLPI.
- `/demo-studio` : état de disponibilité Core/Twin, limites Evidence/GLPI/Policy et provenance SYNTHETIC/REAL à qualifier ; inventaire vide/inaccessible = UNKNOWN.
- `/demo-studio/run/{rid}` : navigation vers les écrans existants avec le même `run_id`, ticket GLPI UNKNOWN.
- `/timeline` : suppression de l'affirmation non attestée selon laquelle les décisions IA enregistrées sont réelles.
- `tests/test_demo_v2.py` : quatre tests ciblés (401, classification, route HTTP, liens du même run).

## Qualification
Commande à exécuter sur ce SHA exact : `PYTHONPATH=app AIOPS_INTERNAL_TOKEN=unit-test-only-demo-v2 python -m unittest discover -s tests -p 'test_demo_v2.py' -v`.
Tests de ce nouveau commit : **NOT_TESTED** au moment de la création ; attendre CI quality.yml et noter le N/N observé dans l'issue #186.
Aucun test Debian, navigateur terrain ou E2E métier. Aucun appel GLPI/HITL, effet LIVE, Docker, modification stable ou secret.
Packaging : `app/portal/main.py` relève de l'image Portal candidate ; le cron stable installé ne le transporte pas automatiquement.
Handoff : 5/5 (consolidation #185), coordination 3/5 pour les futurs statuts auth GLPI/Evidence, 4/5 pour Policy/HITL.
