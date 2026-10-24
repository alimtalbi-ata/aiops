# AIOps — Portail unique et génération de démo basée sur le processus

## Décision d'architecture
**Unique URL publiée : http://10.79.94.202:17777/**. Aucun serveur de démonstration supplémentaire, et abandon du mode d'accès séparé :18777 pour la cible d'intégration. Le NOC est une **route dans la même application** : `/noc`, et un endpoint de lecture `/api/noc/state`. Les routes héritent de l'authentification et du middleware du portail hôte. Ne pas déployer avant validation de cette hypothèse dans le portail actuellement en place.

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
**Livré dans la PR :** contrat de route NOC en lecture seule, validation stricte du read model et tests. **Non livré / non qualifié :** branchement du routeur dans le processus portail actuellement déployé, automatisation de déclenchement sur le webhook réel, observation en temps réel des services, publication sous :17777 et tests E2E Debian. Ce sont des préconditions bloquantes pour déclarer la plateforme fonctionnelle.

## Déploiement contrôlé
1. Inspecter en lecture seule sur Debian quel processus sert :17777, les routes, middleware, identité, proxy, volumes et points d'intégration ; préserver des sauvegardes de configuration.
2. Vérifier le schéma du read model réel et adapter `read_model_callable` sans modifier la politique de production.
3. Valider sur une copie d'intégration avec tests d'authentification, de panne, d'isolation des sources et replay synthétique E2E, sans second port public.
4. Documenter le plan rollback et obtenir accord de bascule avant de modifier le portail déployé.

**Ne pas exécuter le script autonome :18777 en production pour ce mode d'intégration.**
