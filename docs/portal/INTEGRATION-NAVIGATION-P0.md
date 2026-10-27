# Portail unique — navigation et read models P0

## Livraison et origine

Portage ciblé de `app/portal/platform_registry.py` depuis la PR #36 (blob source `969b5f7fdc4f654cca5f6d3b6ed6e2a004f5fd8d`), sans importer les 374 fichiers de cette PR. Les composants restent `UNKNOWN` sans observation fraîche authentifiée. Une URL configurée n'est jamais une preuve de service disponible, une route montée, une capture réelle ou une autorisation LIVE.

Le portail expose `GET /api/portal/components` avec la liste des composants et l'état de configuration des liens. Le Command Center affiche les liens externes explicitement configurés et une navigation interne Runs/Twin/Copilot. Aucun proxy vers n8n, Thruk, Grafana, GLPI ou Checkmk n'est créé. Les liens s'ouvrent dans un nouvel onglet avec `noopener noreferrer` et `no-referrer`.

`GET /api/portal/bootstrap` et la page d'accueil agrègent en lecture seule les APIs existantes `Core /api/dashboard`, `Core /api/runs` et `Twin /api/twin/summary`. En cas de panne, réponse mal formée ou erreur, chaque read model devient `UNKNOWN` avec valeur `null`, jamais une fausse liste vide ou un succès synthétique. `READABLE_UNVERIFIED` signifie seulement qu'une réponse valide a été lue, sans attestation d'authentification runtime.

## Configuration opérateur

Port externe par défaut : `17777`, personnalisable par `AIOPS_PORTAL_HOST_PORT`. La valeur doit être validée dans le Compose du déploiement avant toute bascule; aucune vérification du Debian n'a été réalisée.

Variables optionnelles, toutes vides par défaut :

- `AIOPS_PORTAL_LINK_N8N`
- `AIOPS_PORTAL_LINK_THRUK`
- `AIOPS_PORTAL_LINK_CHECKMK`
- `AIOPS_PORTAL_LINK_GRAFANA`
- `AIOPS_PORTAL_LINK_GLPI`

Utiliser des URL HTTPS complètes sans jeton dans l'URL, ni userinfo, query ou fragment. Pour les services LAN en HTTP sur **IP privée uniquement**, définir explicitement `AIOPS_PORTAL_ALLOW_HTTP_LINKS=true`; cela n'authentifie pas le serveur ni le transport. Les liens invalides sont rejetés sans exposer leur valeur dans la réponse publique. La configuration est relayée par `compose.yml` au seul conteneur portail.

## Contrôles et limites

Tests unitaires : `tests/test_portal_integrations.py` et `tests/test_portal_read_models.py`, inclus dans le workflow qualité existant. Ils ne lancent ni ne simulent un service n8n/Thruk/Grafana/GLPI; les tests d'intégration de ces composants sont **NOT_TESTED**. Le serveur NVIDIA NIM n'est pas appelé.

**Blocages explicites** : authentification utilisateur et RBAC portail non qualifiés; inventaire d'incidents dédié et evidence read model non exposés tant que le contrôle d'accès n'est pas conçu; aucune capture réelle ou authentification de session; Thruk/Checkmk non démontrés en conteneurs CI; aucune qualification runtime sur `10.79.94.202:17777`. Les endpoints existants `/api/demo` et `/api/copilot` conservent leurs règles historiques et nécessitent un durcissement RBAC avant exposition à des utilisateurs non fiables.

## Vérification future

Sur un environnement de développement autorisé, configurer des URLs opérateur réelles et vérifier que `/api/portal/components` expose `CONFIGURED_UNVERIFIED` tout en gardant `state=UNKNOWN`. Exécuter le test de qualification de la stack réelle, puis les parcours navigateur authentifiés. Ne pas transformer un lien qui fonctionne en preuve d'un incident ou d'une exécution n8n.
