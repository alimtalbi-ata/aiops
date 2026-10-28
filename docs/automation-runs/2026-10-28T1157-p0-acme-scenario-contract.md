# 2026-10-28 11:57 CET — P0 ACME contrat scénario/events minimal

## Départ et coordination

- HEAD `main` vérifié avant la branche puis avant ce journal : `7659cc32b573e0bb847221b9d1dc5081039a0f3e` (merge documentation Explore/Story #132).
- Branche dédiée : `feat/p0-acme-scenario-contract-20261028-1153` ; [PR draft #133](https://github.com/alimtalbi-ata/aiops/pull/133) ciblant `main`, sans merge ni modification des autres branches.
- Sources relues : fixture et validateur v1, impact read model, Explore/Story et tests, `.github/workflows/quality.yml`, journaux P0 récents, continuité et décisions, PR #36 et #127, liste des PR ouvertes. #127 propose une extension entreprise 60 CI non fusionnée ; elle ne doit pas redéfinir les IDs du scénario minimal.
- Coordination explicite sur [PR #127](https://github.com/alimtalbi-ata/aiops/pull/127) : commentaire GitHub `6467161314` annonçant le contrat et les espaces d'IDs distincts.

## Micro-livraison et fichiers

- `app/portal/acme_scenario_contract.py` (nouveau) : projection `aiops.acme-scenario.v1` depuis le read model validé, neuf événements `SIM-EVT-ACME-001..009`, liens source SAN P1 / impact Payments P2, labels Run/ticket uniquement synthétiques. Refus si drapeaux runtime, IDs, chemin ou checkpoints incohérents.
- `app/portal/acme_explore_story.py` : GET `/api/demo/acme-scenario` protégé par le viewer Bearer **avant lecture du fixture** ; Explore/Story réutilisent la projection canonique, sans changer leur schéma de réponse ni leurs commandes.
- `tests/test_acme_scenario_contract.py` : six tests (fixture v1, déterminisme, correspondance Explore/Story, refus d'auth avant I/O, falsification et refus fail-closed).
- `.github/workflows/quality.yml` : une étape supplémentaire dans le job existant, sans workflow parallèle.
- `docs/demo/ACME-SCENARIO-CONTRACT-V1.md` : contrat consommateur, exemple JSON et coordination avec #127.
- Ce journal : `docs/automation-runs/2026-10-28T1157-p0-acme-scenario-contract.md`.

Commits de code/tests/docs avant journal : `ab0e2b1cff8d0db312657d6bc7d2934bfc75847a`, `5ddb78231a7b103096fec277f7b0e6e0f87106b0`, `1037392e99c55702fc25ff0a24ae183134c995f0`, `8524b36dec539d07c8b55c9f619e16516436fad5`, `d3e76fd0ab8e66f5f7cfa7d4e1b97cba607dba76`.

## Validation réelle

- [GitHub Actions quality #40675954317](https://github.com/alimtalbi-ata/aiops/actions/runs/40675954317) sur SHA **`d3e76fd0ab8e66f5f7cfa7d4e1b97cba607dba76`** : **SUCCESS** confirmé, jobs `policy-and-static`, `core-postgres-noc-real-integration` et `grafana-real-integration` tous **SUCCESS**.
- Étapes confirmées **SUCCESS** : compilation Python, nouveaux tests de contrat ACME, régressions ACME impact et Explore/Story, syntaxe JS, tests DOM synthétiques, audit statique, Compose config, intégration HTTP réelle Grafana, intégration NOC Core/PostgreSQL réelle.
- Les deux jobs d'intégration utilisent des services éphémères **mais ne testent pas l'API ACME contre Core/GLPI/Temporal**. Les tests du scénario sont des tests HTTP ASGI in-process et des contrats locaux ; ne pas les appeler E2E runtime.
- CI du commit de journal : à vérifier après publication ; aucune conclusion anticipée.

## Contrat, limites, sécurité

- Schéma d'entrée `aiops.acme.demo.v1` intact ; nouveau schéma de lecture `aiops.acme-scenario.v1`. API GET lecture seule et `POST /api/demo/explore-story/control` rétrocompatible. Les mêmes événements sont projetés en Explore et Story.
- `SIMULATED_TARGET` / `SIMULATED_UNVERIFIED` ; aucun ticket GLPI réel, aucun Run Core réel, aucune capture, aucun événement observé. `ticket_id=null`, `event_timestamp_utc=null`, `runtime_attested=false`, `live_remediation_authorized=false`, `backend_writes=false`.
- **NOT_TESTED** : navigateur réel, Core/Temporal/GLPI sur ce parcours, ACL tenant serveur qualifiée, Ollama/NGX, captures et vidéo finale. La protection viewer du fixture fictif ne prouve pas l'isolation tenant de données runtime.
- Aucun SSH, accès Debian, déploiement, migration, remédiation LIVE ou secret de production. Risque de divergence avec #127 si ses IDs entreprise sont traités comme IDs de ce contrat ; mapping explicite requis.

## Prochain micro-lot

Afficher les IDs d'événement et les liens Incident/impact dans le panneau Explore/Story, avec test navigateur réel isolé et capture vérifiable ; puis établir une corrélation indépendante Core/GLPI avec services éphémères et ACL tenant authentifiée. Pas de promotion des checkpoints fictifs en preuve.
