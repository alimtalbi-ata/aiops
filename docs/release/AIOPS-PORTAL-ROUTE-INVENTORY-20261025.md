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
| GET /api/portal/bootstrap | Agrège dashboard, runs et résumé Twin, avec dégradation partielle explicite | Trois lectures HTTP soumises en parallèle, deadline globale de 3 s, sans retry ; pool partagé de six workers et deux requêtes admises simultanément | Une source en retard devient `UNKNOWN` (`UPSTREAM_TIMEOUT` / `READ_DEADLINE_EXCEEDED`) ; le créneau de capacité reste réservé jusqu'à la fin des workers retardataires pour empêcher l'accumulation de tâches. Les autres sources restent disponibles. `_portal.status` vaut COMPLETE ou DEGRADED. Cela ne prouve ni SSO global ni authentification runtime des upstreams. |
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

Le seul point d'entrée demandé est http://10.79.94.202:17777/. Le Compose candidat et `config/.env.example` utilisent désormais 17777 comme port hôte par défaut du portail, en conservant le bind loopback `127.0.0.1` par défaut ; les bindings backend existants restent loopback-only. Cela aligne le numéro de port sans ouvrir de listener réseau public. L'URL sur l'adresse LAN n'est pas prouvée accessible par cette configuration : elle dépend du listener/proxy déjà autorisé sur la cible et doit être qualifiée séparément. Aucun profil Compose, binding, pare-feu, service ou conteneur Debian n'a été modifié.

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

Le parseur du manifeste rejette également les clés JSON dupliquées. Les champs ambigus ne peuvent ainsi pas être interprétés différemment par plusieurs consommateurs JSON ; le test vérifie le refus d'un champ `scenario` dupliqué.

Le manifeste doit avoir un objet JSON comme racine. Les tableaux, scalaires et autres formes JSON valides mais non conformes sont refusés proprement avec le statut de job `failed`, sans exception de type qui remonterait au handler HTTP.


### Barrière de capacité du bootstrap — 27 octobre 2026

Le bootstrap utilise désormais un pool partagé de six workers pour ses trois lectures indépendantes et admet au plus deux requêtes bootstrap simultanées. Une requête supplémentaire échoue immédiatement en HTTP 503 `portal_bootstrap_capacity_exceeded`, au lieu de créer un nouveau pool de threads par requête. Les lectures restent des GET avec `timeout=3` et `retries=0`; la réponse conserve le statut de provenance `UNATTESTED_UPSTREAM_READS`.

Cette limite borne le nombre de workers et la concurrence active, mais ne constitue pas un rate limiter global ni une garantie de disponibilité du runtime. Elle ne change ni le périmètre d'authentification (le bootstrap uniquement), ni les connexions backend. Le test ASGI occupe les six workers avec deux requêtes synthétiques, vérifie que la troisième est refusée, puis libère les lectures ; aucun endpoint upstream réel n'est appelé.



### AioOps-NOC-Offline-Browser-Evidence.zip — inventaire membre par membre (27 octobre 2026)

**Original Library ZIP :** 294 261 octets ; SHA-256 `a8534adaa8fe238ea5173148d2f2fb133cf6917d5f88c185136ea305c0a2c14e` ; `ZipFile.testzip()` = `None` (CRC PASS), 10 membres non-répertoire. Les octets ont été matérialisés en workspace isolé pour inspection ; ni l'archive ni les PNG bruts ne sont copiés dans le dépôt ou le kit.

| Chemin original | Octets | SHA-256 |
|---|---:|---|
| `checkmk-export.png` | 51 619 | `0f1b622d133f381d0db601d40a3eca1890a34cb98361e8d5aaca178fc4d77c91` |
| `evidence-index.json` | 1 274 | `a6f952f90e5920a0f532c7ce5ade33354e1f606d62e6dce73aa721f29205d3f0` |
| `evidence-center.html` | 1 497 | `1319f57887bcd21cb720f0163da754886f6626134df11063d41c12d27ed9b2e2` |
| `manifest.json` | 938 | `17c01a26cf1e6c5fbedc7daec61d3ea31fc275b1996c90840b1c54d54725f499` |
| `star-cue-map.json` | 1 419 | `3b20fbe94d2e6f99da69838bd021d7f7d76c90a3ca5a099c6d066ad8f7a0d200` |
| `star-event-binding.json` | 5 184 | `4a5a7286bce45d3be23a6b32795882213a74bda339c9cb245c7fc843628623f7` |
| `star-events.json` | 2 520 | `6d7b7e4f609961c53998271219b562abc37794ff9f92999f95038b567a237928` |
| `star-trace.html` | 2 931 | `db771acb39fae24fb7df050272fb3f12fc9448aa028b8aa6f17ac4d8c6f5ed15` |
| `synthetic.png` | 95 487 | `61c8290e52edd4338d5f319c7ad3e89ec31e54c96df1390438047f36267f59bc` |
| `unified.png` | 150 565 | `3930128c41629a154f44b54fdccc8471426e5fd087d8e0362a4456c595cae201` |

**Contexte et contrat :** centre de preuves NOC hors ligne ; neuf cues STAR (`detect` à `close`), `RUN-ACME-OFFLINE-STAR`, `INC-ACME-SAN-LOSS`, neuf identifiants d'événement synthétiques et empreintes. Le ticket, l'horodatage runtime et les liens métier authentifiés sont absents. Le manifeste déclare trois `OFFLINE_TEST`, zéro `OBSERVATION`, zéro `RUNTIME_EVIDENCE`, `runtime_authenticated=false` et `live_remediation_authorized=false`. Les trois PNG sont des rendus locaux hors ligne ; leurs associations aux cues sont `ILLUSTRATIVE_ONLY`, pas des écrans Checkmk/GLPI/n8n/Grafana attestés.

**Architecture / interfaces / dépendances :** trois vues HTML statiques, JSON locaux (index, manifeste, cue map, event binding, événements) et trois images. Aucun module Python, adaptateur HTTP, endpoint, Playwright campaign ou dépendance à un service live n'est présent dans cette archive. L'interface est un ensemble de fichiers statiques locaux ; elle ne remplace pas les contrats actuels `star-portal-transport-v1`, `star-event-source-binding` ou le gate Chromium moderne.

**Comparaison et décision de déduplication :** le contrat de liaison événement↔capture est déjà implémenté par `demo/noc_star_event_binding.py` (`aiops-noc-synthetic-star-hash-link-v1`) et couvert par `tests/test_noc_star_event_binding.py` : neuf cues ordonnés, identités synthétiques cohérentes, SHA-256 canonique des événements et des associations capture↔événement, rejet des sources forgées, reproductibilité et `runtime_authenticated=false`. Le JSON archivé est une fixture de sortie, pas un module manquant ; **aucun code n'est importé**. `demo/noc_synthetic_snapshot.py` traite un autre contrat (états synthétiques hôtes/services) et n'est pas remplacé par cet export. Ne pas importer les PNG dans la qualification de captures applicatives, ne pas promouvoir `runtime_authenticated`, ne pas créer de ticket/horodatage fictif et ne pas embarquer l'archive originale dans le kit. Le contrôle hors ligne de cet inventaire a vérifié la structure ZIP, les 10 tailles/hashes et les champs JSON/HTML textuels ; l'absence de correspondance dans un balayage de texte n'est pas une analyse visuelle exhaustive des images.

**Tests de réutilisation à exiger avant migration de données :** comparaison de SHA-256 de chaque membre, validation stricte du manifeste, liaison image↔hash, rejet de `run_id`/cues manquants ou dupliqués, assertion de zéro preuve runtime, puis rendu Chromium local sans réseau. Aucun test de ce ZIP ne qualifie le runtime cible `:17777`.


### Qualification cryptographique locale de l'archive NOC — 27 octobre 2026

Sur les octets originaux matérialisés en workspace isolé, le contrôle complémentaire suivant a été exécuté après l'inventaire :

- ZIP/CRC : PASS ; SHA-256 archive recalculé = `a8534adaa8fe238ea5173148d2f2fb133cf6917d5f88c185136ea305c0a2c14e`.
- Les trois PNG ont été vérifiés contre les trois entrées de `evidence-index.json` et les trois entrées de `manifest.json` : taille et SHA-256 identiques.
- Les neuf événements de `star-events.json` ont été re-hachés à partir de leur JSON canonique et correspondent aux neuf `event_sha256` du binding.
- Les trois associations capture↔événements ont été recalculées selon la sérialisation canonique et correspondent aux trois `binding_sha256`.
- L'ordre des neuf cues correspond au cue map ; `runtime_proof_count=0`, `runtime_authenticated=false`, `live_remediation_authorized=false`. Résultat du contrôle local : PASS, zéro incohérence interne.

Ce PASS établit uniquement l'intégrité et la cohérence internes de cette archive synthétique. Il ne prouve ni la provenance d'une application réelle, ni un timestamp métier, ni un ticket GLPI, ni une observation Checkmk/n8n/Grafana. Les images restent exclues du kit et des captures de qualification runtime.
