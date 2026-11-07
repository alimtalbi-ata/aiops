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
