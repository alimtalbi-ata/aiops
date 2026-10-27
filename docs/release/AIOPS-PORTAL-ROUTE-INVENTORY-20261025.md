# AIOps 2.0 — Inventaire exact des routes et connexions du portail

Date de revue : 26 octobre 2026. Source : code de la branche de continuité de la PR draft #36. Ce document décrit le code et les adaptateurs présents ; il ne prétend pas mesurer le runtime Debian.

## Contrat de présence de route

La route GET /api/platform/components calcule désormais, pour chaque chemin planifié, si un handler GET du même chemin exact existe dans request.app.routes, c'est-à-dire dans la table ASGI du processus qui sert cette requête. Les champs portal_get_path_present et portal_get_path_evidence (EXACT_GET_PATH_MATCH ou NO_EXACT_GET_PATH) décrivent uniquement ce rapprochement. La portée est IN_PROCESS_ASGI_ROUTE_TABLE_ONLY et portal_route_presence_is_runtime_attestation reste false.

Cette présence n'est PAS une attestation que le composant correspondant est branché : par exemple, /noc existe pour afficher cet inventaire statique et /runs existe pour afficher une page portail ; ni l'un ni l'autre ne prouve que Checkmk ou Temporal est connecté. Chaque entrée conserve route_mounted=false, available_in_portal=false, runtime_authenticated=false et requires_route_integration=true jusqu'à une intégration métier séparément revue. Les paramètres de requête du client ne modifient ni les chemins ni les états.

## Routes déclarées par le portail source

Les routes ci-dessous ont été relevées dans app/portal/main.py et les quatre routeurs effectivement inclus par ce fichier (STAR legacy replay, storyboard public, registre de plateforme et read model ACME). La méthode, le handler, les dépendances upstream et les limites sont indiqués pour éviter de confondre une page avec une intégration.

| Méthode et chemin | Comportement présent dans le code | Connexion constatée au niveau source | Limite de qualification |
|---|---|---|---|
| GET /health | État local du handler portail | Aucune | Ne prouve pas la connectivité aux backends ni le port hôte. |
| GET /api/portal/bootstrap | Agrège dashboard, runs et résumé Twin, avec dégradation partielle explicite | Trois lectures HTTP bornées à 3 s chacune, sans retry ; chaque source est lue indépendamment | En cas d'échec ou de réponse JSON non-objet, la section concernée devient UNKNOWN sans détails d'exception/URL ; `_portal.status` vaut COMPLETE ou DEGRADED. Cela ne prouve ni SSO ni authentification runtime. |
| GET / | Cockpit avec incidents/runs et résumé Twin | Lecture Core et Twin | Les erreurs sont rendues INCONNU ; runtime cible non vérifié. |
| GET /runs | Liste des exécutions Core | Lecture Core | Ne monte pas l'API Temporal elle-même. |
| GET /timeline | Incidents, détails de run, ledger et preuves référencées | Lecture Core | La page Evidence globale reste décrite comme adaptateur manquant. |
| GET /twin | Topologie et impact ACME | Lecture Twin | La disponibilité du service Twin n'est pas attestée en production. |
| GET /evidence | Page d'information sur la traçabilité | Contenu statique | Aucun connecteur Evidence transversal n'est appelé par ce handler. |
| GET /policy | Runs bloqués/en attente et explication des barrières | Lecture de la liste Core ; explication locale | Ne crée pas d'approbation HITL. |
| GET /copilot | Interface de conversation | Le navigateur appelle le handler POST /api/copilot | La réponse dépend de l'upstream et n'est pas une preuve en soi. |
| POST /api/copilot | Relaye une requête vers Copilot | POST vers COPILOT_URL + /api/copilot/query | Aucune disponibilité ou identité upstream attestée par le test ASGI. |
| GET /demo-studio | Préflight de démonstration et liste de runs | Lecture Core et Twin | L'écran est une vue, pas la preuve d'un run E2E complet. |
| POST /api/demo | Crée un incident synthétique, crée un run et demande son exécution | Écrit dans Core quand AIOPS_DEMO_LAUNCH_ENABLED=true et un Bearer valide est fourni | Route mutatrice ; ne pas l'appeler en production pendant cette qualification. |
| POST /api/demo-enriched | Même principe pour une variante enrichie | Écrit dans Core si le même opt-in et jeton sont valides | Ne pas l'appeler en production ; le mot synthétique n'élimine pas ses effets sur Core. |
| GET /demo-studio/run/{rid} | Détail et timeline d'un run DEMO/REPLAY/STORY | Lecture Core | Contrôle d'appartenance au registre ; auth runtime non qualifiée ici. |
| GET /api/demo-status/{rid} | État de suivi d'un run de démonstration | Lecture Core | Lecture seule ; résultat inconnu si Core est indisponible. |
| GET /qualification | Affiche une matrice de qualification et ses limites | Contenu local | Les éléments « rapportés » ne sont pas des résultats CI par ce seul affichage. |
| GET /qualification-lab | Prévisualisation de scénarios par graine/mode | Calcul Python local | Simulation narrative uniquement ; pas de prédiction DGX ni d'événement Evidence. |
| GET /acme-stories | Catalogue de récits métier | Contenu local | Pas d'incident créé par cette page. |
| GET /policy-control | État, historique et décisions de simulation Policy | GET via POLICY_URL vers des endpoints Policy | Lecture seule dans ce handler ; le runtime reste à qualifier. |
| GET /policy-story | Histoire interactive locale de refus Policy | Contenu local/synthétique | Pas d'approbation ni de remédiation réelle. |
| GET /demo/ | Catalogue Demo Center synthétique | HTML local | Pas d'appel Core ni d'incident créé. |
| GET /demo/star | Sert un asset HTML local synthétique | Fichier local vérifié comme fichier régulier | Pas de capture d'une application réelle. |
| GET /demo/star-replay/{run_id} | Replay local opt-in à partir d'artefacts JSON et SHA-256 | Lecture locale de fichiers dans le dossier configuré | Les preuves restent synthétiques/non attestées ; pas d'I/O backend runtime. |
| GET /api/platform/components | Registre de 20 familles et présence des chemins GET exacts | Table ASGI locale uniquement | Aucun health check ou appel de service n'est exécuté. |
| GET /noc | Tableau statique de convergence et présence des chemins GET exacts | Table ASGI locale uniquement | Ce n'est pas l'écran NOC runtime et il n'interroge pas Checkmk/Thruk. |

| GET /api/demo/acme-impact | Modèle déterministe de l'impact ACME à partir du fixture local validé | `app/portal/acme-fixtures.json` + `portal.acme_fixture_contract` | Run ID dérivé du SHA-256 ; ticket GLPI réel et horodatage runtime restent absents ; ticket SIM-GLPI et checkpoint fixe sont explicitement fictifs ; aucun backend contacté. |
| GET /demo/acme-impact | Écran HTML local de la même fixture, avec identifiants, chemin et trous de preuve | Même fixture embarqué `app/portal/acme-fixtures.json` et contrat stdlib que l'API JSON | Affiche séparément les champs réels ABSENT et le ticket/horloge de scénario synthétiques ; CSP sans scripts, formulaires, liens ou connexions externes. |

## Interfaces upstream codées mais non qualifiées

Le portail configure CORE_URL, TWIN_URL, COPILOT_URL et, dans la page Policy Control, POLICY_URL. Les appels relevés dans le code concernent Core pour dashboard, incidents, runs, ledgers, preuves et exécution de démonstration ; Twin pour résumé, graphe et impact ; Copilot pour la requête conversationnelle ; Policy pour l'état, l'historique et les décisions de simulation.

La présence de wrappers HTTP et de variables d'environnement dans le dépôt ne prouve pas que les destinations DNS, réseaux, certificats, secrets, permissions et endpoints fonctionnent sur le système cible. Les tests ici sont des tests de code source et des tests ASGI isolés, pas une attestation d'authentification de ces upstreams.

## Familles non raccordées par ce portail source

Aucun handler de connexion directe aux API des produits suivants n'est monté par les routeurs examinés : GLPI/CMDB, n8n, Grafana, Prometheus, Alertmanager, Checkmk, Thruk, Temporal API, DGX Analyst/Critic et le backend RAG. Des fixtures d'intégration ACME, scripts de découverte read-only et adaptateurs NOC existent ailleurs dans le dépôt, mais ils ne deviennent pas des connexions portail parce que leurs fichiers existent.

En particulier, demo/noc_portal_integration.py définit un adaptateur séparé pour /api/noc/state et /noc avec un fournisseur de read model ; ce routeur n'est pas inclus par app/portal/main.py dans la version examinée. Le chemin /noc monté par platform_registry_router.py est seulement l'inventaire statique. Le registre planifie aussi /noc/checkmk, /noc/thruk, /observability/grafana, /observability/metrics, /observability/alerts, /itsm, /workflows, /incidents, /runs/activities, /intelligence, /decisions, /knowledge, /topology, /notifications et /escalations ; la présence effective d'un GET exact est calculée par la nouvelle observation de la table ASGI, sans jamais faire passer cette présence pour une connexion au produit.

## Port unique, runtime cible et limites de sécurité

Le seul point d'entrée demandé est http://10.79.94.202:17777/. Le registre ne change aucune liaison. Le Compose suivi par Git contient historiquement un binding par défaut sur 127.0.0.1:7777 et plusieurs ports de backends : c'est une configuration source, pas la preuve de ce qui tourne sur Debian. Aucun profil Compose, binding, pare-feu, service, conteneur ou port n'a été modifié par cette qualification.

Le scénario ACME SAN P1 → impact Payments P2, les neuf checkpoints d'écran réel, les identifiants run_id/incident_id/ticket_id, les timestamps, les SHA-256 de captures, l'authentification effective, la provenance, le replay déterministe et le passage n8n 02→03 exigent une recette E2E distincte sur un environnement d'intégration isolé. Aucune capture de fixture HTML ne doit être présentée comme une capture GLPI/n8n/Grafana réelle.

## Validation et rollback

Tests concernés : tests/test_platform_registry_portal_route.py, tests/test_noc_portal_integration.py et suites offline du kit cumulatif. Vérification recommandée après chaque changement :
- python -m unittest discover -s tests -p 'test_platform_registry_portal_route.py' -v
- python -m unittest discover -s tests -p 'test_portal_bootstrap_read_model.py' -v
- python -m unittest discover -s tests -p 'test_noc_portal_integration.py' -v
- python -m unittest discover -s tests -p 'test_single_portal_candidate_kit.py' -v
- python -m unittest discover -s tests -p 'test_verify_single_portal_candidate_kit.py' -v

Le changement n'introduit ni appel réseau, ni écriture, ni nouveau port. Le rollback est source-only : revenir au commit parent sur la branche de la PR, relancer les tests offline et régénérer le candidat. Ne pas exécuter d'installateur sur Debian, ne pas redémarrer/recréer les conteneurs V1/containerd et ne pas écrire dans GLPI/n8n/Grafana/DB/CMDB. La production reste NON QUALIFIÉE jusqu'à l'E2E runtime réel, une sauvegarde/restore vérifiée et une approbation humaine explicite.

## Contrat de type strict du read model NOC — 26 octobre 2026

La revue du validateur existant a identifié un cas JSON mal formé : les champs `steps[*].state` ou `items[*].state` peuvent être des tableaux/objets. Tester directement leur appartenance à un `set` Python peut alors lever `TypeError` au lieu d'un rejet de contrat explicite. `demo/noc_portal_integration.py` valide maintenant le type chaîne avant l'appartenance à `VALID_STATES`, à la fois pour les étapes et pour les lignes rendues. Les tests `tests/test_noc_portal_integration.py` couvrent les valeurs listes/objets et exigent une `ValueError` contrôlée ; la route encapsulée continue de répondre sans divulguer d'exception interne.

Ce durcissement ne monte pas le routeur NOC dans `app/portal/main.py`, n'ajoute aucune connexion backend et ne change aucun état de production. `GET /noc` reste l'inventaire statique ; `GET /api/noc/state` reste défini dans l'adaptateur séparé, non monté par le portail examiné. Provenance et authentification runtime restent non attestées tant que le fournisseur réel et son contrôle d'identité ne sont pas raccordés.

## Contrat de dégradation du bootstrap — 26 octobre 2026

GET /api/portal/bootstrap soumet en parallèle les trois lectures indépendantes Core `/api/dashboard`, Core `/api/runs` et Twin `/api/twin/summary` (trois workers au maximum). Chaque appel utilise `timeout=3` et `retries=0` ; leurs délais HTTP ne s'additionnent donc pas comme dans une séquence de trois requêtes. Une source lente ou invalide est normalisée séparément en `UNKNOWN`, sans supprimer les deux autres sections. Aucun POST n'est appelé. Un échec de transport ou une réponse JSON qui n'est pas un objet est normalisé en `status=UNKNOWN`, avec un code d'erreur stable, sans URL, corps upstream ou texte d'exception. Les deux autres sections conservent leur valeur si une source échoue.

La clé additionnelle `_portal` suit `aiops.portal-bootstrap-readmodel.v1`, indique `COMPLETE` ou `DEGRADED`, les noms des sources indisponibles et les barrières `runtime_attested=false` et `live_remediation_authorized=false`. `COMPLETE` signifie uniquement que les trois endpoints ont renvoyé des objets JSON ; ce n'est pas une preuve indépendante d'authenticité, de fraîcheur métier, de SSO ou de connectivité au runtime cible.

### Barrière de lecture opérateur — 27 octobre 2026

`GET /api/portal/bootstrap` exige maintenant un Bearer token dédié `AIOPS_PORTAL_READ_TOKEN`. Si la variable est absente/vide, la route échoue en `503 portal_read_auth_not_configured`; si le jeton est absent ou invalide, elle échoue en `401 invalid_portal_read_token`. La comparaison utilise `hmac.compare_digest`; le jeton de lecture est distinct des jetons internes/admin. `deploy/init-env.sh` le génère aléatoirement, le garde dans `.env` en mode `0600`, préserve sa valeur sur les relances et le transmet uniquement au conteneur portail. Le préflight le traite comme secret requis. Les tests ASGI couvrent succès, secret non configuré, en-tête absent, jeton incorrect et lecture upstream en mode simulé.

Cette modification protège uniquement l'endpoint bootstrap ; elle ne constitue pas une authentification globale du portail. Les pages HTML, `/api/copilot`, autres APIs et upstreams nécessitent encore une frontière d'authentification/SSO distincte et une qualification de déploiement. Ne pas exposer le portail sans proxy d'identité contrôlé. Aucun secret de test n'est un secret de déploiement.


## Isolation du générateur vidéo local

Le lancement opt-in de la vidéo utilise une liste d'autorisation d'environnement pour le processus enfant : PATH, répertoires utilisateur/temporaire, locale et variables explicitement nécessaires au cache Chromium/Playwright et aux polices. Les jetons portail/internal/admin et autres variables d'environnement ne sont pas transmis au rendu synthétique. Ce contrôle réduit l'exposition des secrets ; il ne remplace ni l'authentification globale du portail ni une qualification de runtime.


## Lecture du manifeste de vidéo

Le processus de statut ouvre le manifeste de sortie avec `O_NOFOLLOW`, exige un fichier régulier non vide, limite sa taille à 64 Kio et vérifie que la taille ne change pas pendant la lecture. Une plate-forme qui ne fournit pas `O_NOFOLLOW` échoue en mode fermé. Un test couvre le manifeste symbolique pointant vers un fichier externe. Ce contrôle concerne la lecture du manifeste et ne constitue pas une qualification complète contre toutes les courses de fichiers du répertoire de sortie.
