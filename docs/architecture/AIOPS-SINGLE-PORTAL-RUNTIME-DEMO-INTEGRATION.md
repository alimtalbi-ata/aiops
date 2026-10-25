# AIOps — Portail unique et génération de démo basée sur le processus

## Décision d'architecture
**URL cible unique : http://10.79.94.202:17777/**. Aucun serveur de démonstration supplémentaire. Le code actuel enregistre `GET /api/platform/components` sur la même application ; cette route ne sert que l'inventaire statique. Les routes NOC alimentées par un read model — `/noc` et `/api/noc/state` — restent dans un routeur distinct et ne sont pas montées dans `portal.main:app`. L'authentification runtime et le bind réel sur :17777 ne sont pas attestés.

## Contrat développé
Le fichier `demo/noc_portal_integration.py` propose `create_noc_router(read_model)` : il ne crée ni serveur, ni listener, ni tâche périodique. Après qualification de l'application et des dépendances, l'application FastAPI existante peut inclure `app.include_router(create_noc_router(read_model_callable))`.

`read_model_callable` doit venir **du pipeline effectivement exécuté par les services AIOps**, pas d'un JSON statique : détection → corrélation → intelligence DGX → critic → policy/HITL → ticket GLPI → notification → evidence/verification. L'identifiant `run_id`, `incident_id`, l'horodatage UTC et l'état de chaque étape doivent être retournés par les services réels, avec contrôle d'origine par le portail. Ne pas attribuer `runtime_authenticated=true` à un événement de démonstration synthétique sans authentification du producteur et contrôles de provenance.

Si les données sont absentes, incohérentes ou non authentifiées, l'API retourne HTTP **503** ; aucune fausse donnée d'exemple ne remplace les résultats. Le NOC reste strictement en lecture seule.

## Automatisation de la démo — architecture cible
- Déclencheur depuis le portail unique : lancement d'un scénario explicitement `SIMULATION`, sous permission et environnement d'intégration dédié.
- Le scénario est injecté dans le vrai webhook d'entrée AIOps via le moteur de replay existant, sans création d'un chemin parallèle.
- Chaque transition est associée à l'identité run/incident, aux signaux Checkmk/Thruk, aux décisions Analyst/Critic, à l'état policy/HITL, aux tickets GLPI et à leurs preuves ; les absences restent `UNKNOWN`.
- Le portail doit consommer des read models de ces services et actualiser la timeline et les captures seulement après une vérification de provenance.
- Captures Grafana/n8n/GLPI : distinguer captures réelles du navigateur sur l'environnement d'intégration et captures synthétiques. Pas d'émulation présentée comme réel.
- Actions LIVE interdites dans la démonstration ; aucune remédiation sans autorisation indépendante.

## État réel de la livraison
**Livré dans la PR :** endpoint de registre statique `GET /api/platform/components` enregistré dans le code source du portail existant ; contrat NOC séparé en lecture seule et tests synthétiques. **Non livré / non qualifié :** montage de `/noc` et `/api/noc/state`, fournisseur issu du vrai pipeline, connexions aux applications, authentification runtime, bind sur `10.79.94.202:17777` et E2E Debian. Ces éléments restent bloquants.

## Déploiement contrôlé
1. Inspecter en lecture seule sur Debian quel processus sert :17777, les routes, middleware, identité, proxy, volumes et points d'intégration ; préserver des sauvegardes de configuration.
2. Vérifier le schéma du read model réel et adapter `read_model_callable` sans modifier la politique de production.
3. Valider sur une copie d'intégration avec tests d'authentification, de panne, d'isolation des sources et replay synthétique E2E, sans second port public.
4. Documenter le plan rollback et obtenir accord de bascule avant de modifier le portail déployé.

**Ne pas exécuter le script autonome :18777 en production pour ce mode d'intégration.**


## Précision sur le registre statique (25 octobre 2026)

Le nouvel endpoint est un read-only plan, sans requête vers Checkmk/Thruk, GLPI, n8n, Grafana, Prometheus, Temporal, DGX ou CMDB. Il renvoie vingt entrées `UNKNOWN`, timestamps absents, `route_mounted=false` et `runtime_authenticated=false`. Il ne démontre ni le montage de ces routes dans le déploiement, ni SSO, ni la provenance des signaux. Pour brancher le NOC réel, l'application existante doit fournir un adapter authentifié et testé, puis inclure le routeur NOC uniquement après revue de ses dépendances et du middleware de sécurité.
