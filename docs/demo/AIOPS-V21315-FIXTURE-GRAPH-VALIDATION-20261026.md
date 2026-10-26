# ACME V2.13.15 — validation du graphe d'impact synthétique

**Date :** 26 octobre 2026  
**Statut :** contrat source/CI uniquement ; aucune qualification runtime ou production.

## Source et réutilisation historique

La validation durcit les fichiers déjà présents, sans recopier ni réécrire le kit d'intégration :
- fixture historique/CLI : `demo/integrations/v21315/acme-fixtures.json` et `demo/integrations/v21315/validate_fixture.py` ;
- contrat canonique stdlib embarqué dans l'image portail : `app/portal/acme_fixture_contract.py` ;
- copie de fixture embarquée : `app/portal/acme-fixtures.json` (octets comparés à l'original par les tests) ;
- contexte d'intégration et limites : `demo/integrations/v21315/README.md` et `docs/recovery/OCTOBER-2026-ARCHIVE-CONTEXT-AND-REUSE.md`.

Au début de ce changement, le fixture portait le Git blob SHA `ad91678e81c6875a94e699d37645a971615dfb1e`. Il s'agit d'un identifiant d'objet Git, pas du SHA-256 des octets du fichier. Les SHA-256 des archives historiques originales sont consignés dans le registre de récupération ; les originaux ne sont pas réemballés ici.

## Besoin métier et contrat

Le scénario pédagogique doit démontrer une relation d'impact explicite : incident synthétique **SAN P1** sur `SAN-FABRIC-A` affectant, par le graphe de dépendances, l'application **Payments P2** `APP-PAY-01`. Une simple existence des deux incidents ne suffit pas.

Le validateur vérifie :
- le schéma/version, la provenance `SIMULATED_TARGET` et l'organisation `ACME-DEMO` ;
- l'unicité des identifiants CI/incidents, l'absence de champs inattendus et la résolution de toutes les références ;
- l'absence de doublons de dépendances et de cycles dans le graphe ;
- les incidents canoniques `ACME-DEMO-SAN-001` (P1) et `ACME-DEMO-PAY-002` (P2) ;
- un chemin de dépendances déterministe du SAN vers Payments ;
- le statut `simulated`, `live_remediation=false` et une allowlist stricte (`analyze`, `notify_dry_run`) ;
- le rejet des clés JSON dupliquées, ainsi que des erreurs actives sous `python -O` (la validation n'utilise pas `assert`).

Le chemin d'impact calculé est renvoyé en sortie CLI pour rendre la cinématique vérifiable. Le code ne contacte aucun endpoint, n'importe rien dans GLPI, n8n, Grafana ou CMDB et ne crée aucun ticket ni incident.

## Architecture, interfaces et dépendances

Entrée CLI : document JSON local, par défaut `demo/integrations/v21315/acme-fixtures.json`. Le CLI historique réexporte `load_fixture(path)`, `load_fixture_bytes(bytes)` et `validate_fixture(data)` depuis le contrat commun. Le read model du portail lit `app/portal/acme-fixtures.json`, puis appelle ce même contrat et calcule le digest sur les octets exacts validés.  
Sortie CLI : résumé déterministe avec nombres de CI/incidents et chemin d'impact, ou code de sortie non nul en cas de violation.  
Dépendances du contrat : bibliothèque standard Python uniquement. Le portail ajoute FastAPI, déjà requis par l'application ; aucun appel réseau n'est exécuté pour ce read model.

Le workflow `.github/workflows/acme-v21315-fixture-validation.yml` compile le wrapper, le contrat et le read model, exécute la fixture de référence et les tests unitaires, dont un subprocess Python optimisé qui doit encore rejeter un graphe sans impact. Il construit ensuite l'image depuis `app/` et lance un smoke test Python du read model dans un conteneur éphémère, avec `--entrypoint python`, sans démarrer Uvicorn ni publier de port.

## Qualification et limites

Cette qualification prouve uniquement le contrat des données synthétiques. Elle ne prouve pas le mapping natif GLPI 11, l'import n8n, une datasource Grafana, un événement Prometheus, une identité authentifiée, une capture Chromium d'un vrai écran ou le fonctionnement E2E du portail `:17777`.

Les composants historiques F20.13/Playwright restent à inspecter et à qualifier séparément. Aucun fragment tronqué n'est déclaré source complète. Aucune capture réelle, aucun secret, token, profil de navigateur ou donnée privée n'est requis par ces tests.

## Rollback

Le changement est limité aux sources, tests et documentation sur la branche de la PR. Le rollback source-only consiste à revenir au commit du changement, puis à relancer les tests hors ligne. Aucun changement de production, réseau, port, conteneur, base, ticket, workflow n8n actif ou remédiation LIVE n'est réalisé.
