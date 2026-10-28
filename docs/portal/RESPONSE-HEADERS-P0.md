# P0 — En-têtes de sécurité du portail

## Portée

Le portail FastAPI existant sur le port cible 17777 applique à ses réponses HTTP traitées : `Cache-Control: no-store`, `Pragma: no-cache`, `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Content-Security-Policy: frame-ancestors 'none'`, `Referrer-Policy: no-referrer` et `Permissions-Policy` interdisant caméra, microphone et géolocalisation.

La protection s'applique aussi aux erreurs HTTP gérées (404, 405, 422). Elle limite la mise en cache de données d'exploitation et le clickjacking. Elle ne constitue **ni authentification, ni RBAC, ni preuve LIVE**. Les réponses 500 générées en dehors de la pile de middleware ASGI, notamment par le gestionnaire d'erreurs serveur, restent à qualifier séparément. Aucun CSP `script-src` strict n'est ajouté car l'interface historique utilise du JavaScript intégré : ce chantier demande une migration contrôlée.

## Qualification

`tests/test_portal_security_headers.py` exécute des requêtes HTTP ASGI isolées contre l'application FastAPI, sans appeler Core, Twin, n8n, Thruk, Grafana, GLPI ni NGX. Le workflow existant `.github/workflows/quality.yml` exécute ces tests ; le résultat réel doit être consulté dans GitHub Actions.

Les intégrations conteneurs éphémères, l'authentification globale, le RBAC par tenant, le navigateur réel et Debian restent **NOT_TESTED**. Aucun endpoint n'est promu LIVE par ce changement.

## Rollback

Retirer l'appel `app.add_middleware(PortalSecurityHeaders)` et son import dans `app/portal/main.py` (revert de la PR) ; ne pas modifier les configurations de production.
