# GLPI — API, authentification, tickets et intégration AIOps2

**État au diagnostic FS1139 : authentification bloquée par restriction IP.** Aucune création réelle de ticket par FS1136 n'a été démontrée. Ce document distingue code, configuration observée et travail restant.

## 1. Instance déjà existante

Dans `compose.yml` :
- Service GLPI : `aiops2-glpi`, conteneur observé `aiops2-rebuild-glpi`, image observée `glpi/glpi:11.0.9`, interne HTTP 80.
- Service DB : `aiops2-glpi-db`, conteneur `aiops2-rebuild-glpi-db`, MariaDB 11.4, base `glpi`.
- Réseau déclaré : `aiops2-integration` ; port hôte par défaut configurable `AIOPS_GLPI_HOST_PORT=8080`.
- Fichier de jeton technique existant et lisible : `/var/glpi/aiops-tech-api.token`. **Ne jamais afficher, copier, committer ou journaliser sa valeur.**
- Un fichier `glpicrypt.key` existe ; il ne doit pas être traité comme un jeton API.

## 2. API REST et authentification

L'intégration FS1136 (`app/core/glpi_client.py`) cible la REST historique :
1. `GET /apirest.php/initSession` avec `Authorization: user_token <secret>` et, si configuré, `App-Token: <secret>`.
2. `POST /apirest.php/Ticket` avec `Session-Token`, `App-Token` si nécessaire, et `{"input":{"name":"[DEMO] ...","content":"...","type":1,"status":1,"priority":...}}`.
3. Confirmation uniquement si l'API renvoie un identifiant numérique positif.
4. `GET /apirest.php/killSession` pour fermer la session.

GLPI 11 présente aussi `/api.php` ; **ne pas supposer que les contrats REST historique et nouvelle API sont interchangeables**. Les sondes FS1138 ont testé `/api.php/v1/initSession` mais n'ont pas validé ce chemin.

Variables attendues dans le code FS1136 : `AIOPS_GLPI_URL`, `AIOPS_GLPI_APP_TOKEN`, `AIOPS_GLPI_USER_TOKEN`, `AIOPS_GLPI_TIMEOUT_SECONDS`, `AIOPS_GLPI_TICKETS_REQUIRED`. Leur présence dans le code **n'atteste pas** leur injection dans Core. Le fichier de jeton GLPI contient un user token selon le diagnostic FS1138 ; aucun app token n'y a été trouvé. Cela ne prouve pas qu'un app token n'existe nulle part ailleurs.

## 3. Incident avéré : ERROR_NOT_ALLOWED_IP

FS1137 :
- `GET /` : HTTP 200 ;
- `GET /apirest.php` : HTTP 400 ;
- `GET /api.php` : HTTP 403.

FS1138 : avec le jeton technique existant, `/apirest.php/initSession` et `/api.php/v1/initSession` ont tous deux renvoyé **HTTP 400, `ERROR_NOT_ALLOWED_IP`**. L'authentification n'a pas abouti ; aucun ticket créé.

FS1139 : la table `glpi_apiclients` existe et comprend `ipv4_range_start`, `ipv4_range_end`, `ipv6`. La sonde depuis `127.0.0.1` dans GLPI renvoie elle aussi `ERROR_NOT_ALLOWED_IP`. Cela suggère une règle de client API restrictive, mais **aucune ligne de règle ni son association au jeton n'a encore été inspectée** : ne pas attribuer la cause à une entrée précise sans preuve.

Topologie réseau observée :
- GLPI : `aiops2-rebuild-integration` (172.19.0.3) et `aiops2-rebuild-public` (172.21.0.6).
- Core : `aiops2-rebuild-control` (172.22.0.8) et `aiops2-rebuild-data` (172.24.0.5).
- **Aucun réseau Docker partagé observé entre Core et GLPI.** Le nom `aiops2-glpi` ne doit donc pas être supposé joignable depuis Core avant correction contrôlée du réseau ou adoption d'une passerelle d'intégration existante.
- Les champs `gateway=invalid IP` du diagnostic sont des valeurs de rendu Docker, pas une preuve d'erreur réseau.

### Procédure de résolution sûre

1. Sauvegarder les paramètres de clients API et documenter l'état avant modification.
2. Examiner **en lecture seule** les lignes `glpi_apiclients` et les options de filtrage IP, sans révéler les jetons. Vérifier si le client AIOps attendu est activé et quelle plage source est autorisée.
3. Déterminer l'adresse source **réelle du futur appel Core → GLPI** après validation du chemin réseau. Une requête depuis la boucle locale GLPI ne simule pas Core.
4. Corriger uniquement la règle du client technique concerné ; ne jamais désactiver globalement les restrictions IP ou ouvrir une plage arbitrairement large.
5. Retester `initSession`, les droits de lecture et les droits de création sur un ticket DEMO unique, avec un marqueur de corrélation unique.
6. Vérifier le ticket dans GLPI et son association persistée dans Core, puis seulement activer la synchronisation en volume.

## 4. Flux DEMO obligatoire, idempotence et KPI

Dans le code GitHub FS1136 :
- `app/core/glpi_ingest.py` : `ensure_ticket` appelé par `POST /api/incidents` **si** `AIOPS_GLPI_TICKETS_REQUIRED=true`.
- `app/core/glpi_client.py` : API REST, préfixe `[DEMO]`, contenu incluant `incident_id` et `external_id`.
- `scripts/fs/fs1136_glpi_outbox.py` : reprise limitée des incidents dont `external_id` commence par `FS1130-`.
- `app/core/glpi_kpi.py` : `GET /api/kpi/glpi` ; `app/portal/kpi_views.py` : affichage KPI si endpoint déployé.

Registre `aiops.glpi_ticket_links` : `incident_id` unique, `glpi_ticket_id` unique, `state` parmi `PENDING`, `CLAIMED`, `CONFIRMED`, `UNKNOWN`, `ERROR`. Un timeout après `POST Ticket` peut signifier qu'un ticket a été créé malgré une réponse absente. **`UNKNOWN` impose une recherche/reconciliation dans GLPI avant tout nouvel essai**, afin de ne pas créer de doublon. Le simple marquage `[DEMO]` n'assure pas l'unicité côté GLPI.

Limites du code actuel à qualifier avant déploiement :
- L'appel GLPI est synchrone dans l'ingestion Core ; la création Core peut être persistée alors que l'API répond 503 après échec GLPI. Un retour 503 **n'implique donc pas absence d'incident Core**.
- L'outbox est créée à l'exécution, pas par migration dédiée ; vérifier le modèle de déploiement/migration avant mise en service.
- L'état `CLAIMED` après crash et `UNKNOWN` nécessitent une procédure explicite de rapprochement ; aucun retry aveugle.
- Les tests FS1136 ont utilisé un **mock HTTP GLPI**, pas un serveur GLPI réel.
- La valeur `configured=true` du KPI indique l'existence du registre, **pas** une session GLPI active.

## 5. Chiffres et preuves connues

- FS1135 : 22 runs FS1130 dans la base au moment du test ; 0 `RESOLVED`, 0 `BLOCKED`, 0 `FAILED` ; ne pas extrapoler à 50 runs.
- FS1136 : 24 incidents FS1130, tous synthétiques, registre `aiops.glpi_ticket_links` absent à cet instant.
- FS1138 : jeton utilisateur présent dans le fichier GLPI, app token non trouvé dans ce fichier, `ERROR_NOT_ALLOWED_IP`.
- FS1139 : champs de plages IP de `glpi_apiclients` confirmés, réseaux Core et GLPI disjoints, boucle locale refusée.

**Aucun de ces constats ne prouve qu'aucun ticket préexistant n'existe dans GLPI.** Le rapprochement avec `glpi_tickets` reste à réaliser.

## 6. Interdictions opérationnelles

Ne pas modifier la production Portal sur 7777 sans autorisation distincte. Ne pas modifier directement `glpi_tickets` pour contourner les contrôles API. Ne pas divulguer de secrets, désactiver le filtrage IP global, connecter Core à tous les réseaux sans revue, ni créer automatiquement 24/50 tickets avant test réel d'un ticket et vérification de déduplication.

## 7. Scripts de diagnostic

`scripts/fs/FS.1137-existing-glpi-api-readonly-discovery.sh` : routes et présence de configuration.  
`scripts/fs/FS.1138-glpi-existing-token-auth-readonly.sh` : tentative d'authentification avec jeton existant, sans création.  
`scripts/fs/FS.1139-glpi-ip-allowlist-readonly.sh` : schéma IP et réseaux.  
`scripts/fs/FS.1136-isolated-glpi-and-readonly-baseline.sh` : test isolé mock + état Core en lecture seule.

Ces scripts ne remplacent ni la qualification réelle de l'API ni la vérification des règles effectives.

## 8. FS1140 — inspection des règles réelles et des tickets préexistants

Script : `scripts/fs/FS.1140-glpi-client-rules-and-existing-tickets-readonly.sh` (`CODE`, pas encore `OBSERVÉ`). Lit uniquement les colonnes non secrètes de `glpi_apiclients` (identifiant, nom, état, plages IPv4/IPv6), le nombre de tickets mentionnant `FS1130`, le nombre de tickets dont le titre commence par `[DEMO]`, et les réseaux des conteneurs Core et GLPI. **Aucune modification**, aucun jeton ni contenu de ticket affiché. Les nombres de tickets constituent des indices de rapprochement, pas des preuves d'unicité ou de corrélation exacte.

Si une règle bloque la boucle locale, ne pas l'élargir automatiquement : vérifier le client associé au jeton, le chemin d'accès futur depuis Core et les droits de création avant une correction ciblée. Les résultats du script doivent être ajoutés ici une fois exécutés.

## 9. FS1140 — résultats observés sur SRV-DEB-05

**Statut : OBSERVÉ, lecture seule, aucune mutation.** Une seule ligne `glpi_apiclients` : `id=1`, nom `full access from api`, `is_active=1`, `ipv4_range_start=2887057410`, `ipv4_range_end=2887057410`, `ipv6=::1`. Les bornes IPv4 correspondent à **172.21.0.2/32** (adresse unique, pas plage étendue). La sonde FS1138 depuis `127.0.0.1` est donc hors de cette autorisation IPv4. Il reste à identifier le détenteur de 172.21.0.2 et le chemin d'accès attendu, sans modifier globalement les ACL.

Résultat FS1140 : `glpi_tickets` contient **0** ticket dont `name` ou `content` mentionne `FS1130` ; **0** ticket dont `name` commence par `[DEMO]`. Ces filtres ne prouvent pas l'absence de tout ticket GLPI préexistant associé par une autre convention.

Réseaux observés : Core uniquement `aiops2-rebuild-control` et `aiops2-rebuild-data` ; GLPI uniquement `aiops2-rebuild-integration` et `aiops2-rebuild-public`. Pas de réseau partagé. Ne pas connecter des conteneurs à un réseau ni changer une ACL sans sauvegarde, validation du chemin et plan de retour arrière. Prochaine étape : identification en lecture seule de l'adresse 172.21.0.2, vérification de l'architecture de proxy/API et test d'authentification depuis la source autorisée (sans exposer les jetons).

## 10. FS1141 — propriétaire de l'adresse autorisée confirmé

**OBSERVÉ** : `172.21.0.2` sur `aiops2-rebuild-public` appartient au conteneur **`aiops2-rebuild-portal`**, portail de production publié sur le port 7777. GLPI est `172.21.0.6` sur ce réseau ; client API GLPI unique `id=1`, actif, `172.21.0.2`–`172.21.0.2`, IPv6 `::1`. Cela explique le refus IPv4 depuis `127.0.0.1` et montre que Core n'est pas actuellement dans la liste d'adresses autorisées. L'intention historique de faire passer les appels par Portal reste une **hypothèse**, non une preuve de flux applicatif. Aucun ticket FS1130 ni titre `[DEMO]` trouvé par les filtres FS1140.

**Prochaine validation** : sonder sans authentification le chemin HTTP depuis Portal vers GLPI pour distinguer connectivité, filtrage IP et authentification ; inspecter uniquement les noms des variables GLPI présentes dans Portal, sans secrets. `docker exec` pour une requête HTTP en lecture seule n'implique pas un redéploiement de Portal. Ne pas déplacer le jeton GLPI dans Portal, ne pas modifier les ACL, ne pas connecter Core au réseau public sans architecture approuvée.

## 11. FS1142 — configuration historique Portal retrouvée

**OBSERVÉ** : le conteneur `aiops2-rebuild-portal` possède les variables `GLPI_API_URL`, `GLPI_APP_TOKEN`, `GLPI_USER_TOKEN` (noms seulement, valeurs non exposées). Depuis ce conteneur, les GET sans jeton vers `http://aiops2-glpi/apirest.php/initSession` et `http://aiops2-rebuild-glpi/apirest.php/initSession` atteignent GLPI et renvoient HTTP 400 `ERROR_APP_TOKEN_PARAMETERS_MISSING`, **pas** `ERROR_NOT_ALLOWED_IP`. La connectivité DNS/HTTP et le franchissement du contrôle IP depuis Portal sont donc établis ; l'authentification et les droits de création restent non validés.

**FS1143 (CODE, exécution attendue)** : `scripts/fs/FS.1143-portal-existing-glpi-credentials-auth-readonly.sh` utilise les trois variables existantes directement dans le processus du conteneur Portal, sans les imprimer, pour `initSession`, `getMyProfiles`, lecture limitée d'un ticket et `killSession`. Aucun POST de ticket, aucun changement de fichiers, aucune relance du Portal. Le chemin historique Portal → GLPI est confirmé pour le transport, mais **ne pas faire de Portal un proxy de tickets pour Core sans revue d'architecture**.

## 12. FS1143 — échec de prévalidation d'URL, pas d'authentification

**OBSERVÉ** : les trois variables Portal `GLPI_API_URL`, `GLPI_APP_TOKEN`, `GLPI_USER_TOKEN` sont présentes. FS1143 s'est arrêté avant `initSession` avec `UNEXPECTED_GLPI_URL_HOST_OR_SCHEME` car le script n'autorisait que `http://aiops2-glpi` et `http://aiops2-rebuild-glpi`. Ce résultat **ne prouve pas** un défaut de jeton ni une panne GLPI. FS1144 (`scripts/fs/FS.1144-glpi-portal-url-shape-readonly.sh`) décrit uniquement le schéma, hôte, port, chemin et résolution DNS de l'URL configurée, sans envoyer de jetons ; vérifier le résultat avant d'autoriser la cible de la prochaine sonde authentifiée.

## 13. FS1144 — URL historique validée et FS1145

**OBSERVÉ** : `GLPI_API_URL=http://172.21.0.6/apirest.php` dans l'environnement du Portal ; jetons application et utilisateur présents, non divulgués. `172.21.0.6` est l'adresse GLPI sur le réseau `aiops2-rebuild-public`. L'arrêt FS1143 venait de son allowlist de noms DNS et **non** d'une erreur de jeton ou d'API.

**FS1145 (CODE, exécution à confirmer)** : `scripts/fs/FS.1145-glpi-auth-existing-portal-ip-readonly.sh` accepte uniquement l'URL historique exacte, utilise les jetons déjà injectés dans Portal pour `GET initSession`, `GET getMyProfiles`, `GET Ticket?range=0-0`, `GET killSession` et n'affiche ni secrets, ni profils, ni tickets. Aucune création de ticket ni modification de Portal. Ce test prouve l'authentification seulement si `session_established=true` est effectivement observé.

## 14. FS1145 — authentification réelle validée ; FS1146 — ticket DEMO unique

**FS1145 OBSERVÉ** : `GET initSession` HTTP 200 avec `session_established=true`, `GET getMyProfiles` HTTP 200, `GET Ticket?range=0-0` HTTP 206 (réponse partielle paginée), `GET killSession` HTTP 200. Les jetons historiques Portal sont valides ; aucun ticket créé ni fichier Portal modifié.

**FS1146 CODE, NON ENCORE EXÉCUTÉ** : `scripts/fs/FS.1146-one-real-glpi-demo-ticket.sh` utilise ces jetons depuis un processus éphémère dans le conteneur Portal, cherche le marqueur fixe `AIOPS-FS1146-GLPI-DEMO-SMOKE-V1` via `search/Ticket`, et ne crée qu'un seul ticket si aucun résultat n'est trouvé. Après `POST /Ticket`, il vérifie `GET /Ticket/{id}` et la corrélation dans le titre. Il ne redémarre ni ne modifie les fichiers Portal, mais **crée volontairement un objet métier réel GLPI** ; exécution autorisée par la demande explicite de tickets DEMO réels. En cas d'incertitude POST, ne pas relancer avant vérification manuelle GLPI. Une recherche par titre ne constitue pas une garantie d'unicité atomique en présence d'exécutions concurrentes : lancer le test une seule fois à la fois.

La réussite de FS1146 n'implique pas encore la réussite du flux **Core → GLPI** : le chemin réseau Core est toujours absent et le code FS1136 n'est pas déployé.

## 15. FS1146 — premier ticket GLPI réel confirmé

**OBSERVÉ SUR SRV-DEB-05** : `scripts/fs/FS.1146-one-real-glpi-demo-ticket.sh` a ouvert une session HTTP 200, recherché le marqueur fixe `AIOPS-FS1146-GLPI-DEMO-SMOKE-V1` (0 correspondance), créé **un ticket réel GLPI id=155** via `POST /Ticket` HTTP 201, puis vérifié `GET /Ticket/155` HTTP 200 avec `correlation_verified=true`. Fermeture de session HTTP 200. `PASS_ONE_REAL_DEMO_TICKET`, `new_tickets_created=1`. Pas de redémarrage ni modification de fichiers Portal.

**Périmètre de la preuve** : création directe depuis le conteneur Portal, avec ses jetons historiques ; **pas** encore création depuis Core, ni corrélation persistée dans `aiops.glpi_ticket_links`, ni KPI de bout en bout. Le ticket #155 est une qualification API autonome. Pour le retrouver, rechercher son marqueur exact dans GLPI. Le test ne doit pas être relancé en parallèle ; après un résultat incertain, rapprochement manuel avant nouvelle tentative.

**Prochaine architecture** : le réseau Core n'est pas commun avec GLPI et son adresse n'est pas autorisée. Ne pas faire dépendre la production d'un `docker exec` dans Portal. Préparer un chemin d'intégration dédié (service/sidecar ou réseau d'intégration et client API dédié avec ACL restreinte), un stockage des secrets hors dépôt, une migration de l'outbox, puis un vrai test Core → GLPI avec déduplication et KPI. Aucun changement du conteneur Portal 7777 sans autorisation distincte.

## 16. FS1147 — corrections Core et régression isolée

**CODE** : `app/core/glpi_client.py` accepte maintenant `AIOPS_GLPI_URL` avec ou sans suffixe `/apirest.php`, conformément à la configuration historique Portal validée. Les réponses GLPI `POST /Ticket` dont l'identifiant est une chaîne décimale sont converties en entier ; autres formes rejetées. La validation URL rejette identifiants intégrés, query et fragment. Commit `b3968a8`.

**TEST ISOLÉ NON ENCORE EXÉCUTÉ SUR LE SERVEUR** : `scripts/fs/FS.1147-core-glpi-client-regression.sh` démarre un faux serveur GLPI sur loopback, charge le vrai module Core, vérifie `initSession → POST Ticket → killSession`, titre `[DEMO]`, corrélation et réponse id `\"155\"`. Il ne touche ni GLPI réel ni Portal. **Ce test ne valide pas l'outbox Postgres, le réseau Core→GLPI, ni la création d'un ticket réel depuis Core**. Prochaine phase : environnement d'intégration dédié, ACL GLPI spécifique à Core et secrets sécurisés, puis test de bout en bout sur un incident.

## 17. FS1147 — résultat exécuté sur SRV-DEB-05

**TEST ISOLÉ OBSERVÉ PASS** : `FS1147_FINAL_STATUS=PASS_ISOLATED` ; `numeric_string_ticket_id_accepted=true`, `historical_apirest_url_accepted=true`, `synthetic_ticket_label=true`, `incident_correlation=true`, `requests=3`, `real_glpi_mutation=false`. Le test a exécuté le module `app/core/glpi_client.py` réel contre un mock local. Il n'a pas créé de ticket GLPI réel et n'a pas prouvé le fonctionnement de l'outbox, du réseau Core, ni de l'ingestion obligatoire. FS1146 reste la preuve distincte de création réelle du ticket #155 depuis Portal.

## 18. FS1148 — test des invariants outbox sur le vrai PostgreSQL Core

**FS1147 OBSERVÉ PASS_ISOLATED** sur SRV-DEB-05 : client GLPI Core chargé contre mock, 3 requêtes, URL historique, ID numérique en chaîne, étiquette DEMO et corrélation validés ; aucune mutation GLPI réelle.

**FS1148 CODE, EXÉCUTION ATTENDUE** : `scripts/fs/FS.1148-real-core-postgres-outbox-rollback-test.sh` exécute Python/psycopg dans le conteneur Core existant. Il lit un incident FS1130 réel, crée une **table PostgreSQL temporaire** avec les contraintes de l'outbox, vérifie insertion idempotente, claim unique, confirmation, absence de reprise d'une ligne CONFIRMED et absence de reprise d'une ligne UNKNOWN. Toutes les opérations ont lieu dans une transaction explicitement annulée ; **aucune écriture persistante** dans `aiops.glpi_ticket_links`, aucun ticket GLPI créé, aucun changement Portal. L'ID 155 est utilisé comme valeur de test dans la table temporaire et **ne constitue pas une liaison réelle** avec un incident FS1130. Ce test qualifie les invariants SQL sur le serveur réel, mais **ne teste pas encore le code de synchronisation FS1136 ni le chemin réseau Core → GLPI**.

## 19. FS1148 — résultat exécuté sur PostgreSQL Core

**OBSERVÉ PASS_ROLLED_BACK** sur SRV-DEB-05 : `fs1130_incident_found=true`, `real_postgres=true`, `duplicate_prevented=true`, `claim_once=true`, `confirmed_not_reclaimed=true`, `unknown_not_retried=true`, `persisted_changes=false`, `glpi_tickets_created=0`. Les assertions portaient sur une table **temporaire**, pas sur le synchroniseur FS1136 ni sur `aiops.glpi_ticket_links`. Le ticket GLPI #155 n'est pas lié à un incident Core. Le prochain jalon reste un vrai flux Core → GLPI avec accès réseau dédié, client GLPI autorisé, secret sécurisé et vérification de l'outbox/KPI.
