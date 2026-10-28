# P0 — Navigation authentifiée des intégrations (2026-10-28)

## Contrat et portée

- Le HTML public du portail ne sérialise plus les URL d'intégration configurées. Il présente des états `UNKNOWN` jusqu'à une action explicite de l'opérateur.
- `GET /api/portal/components` réutilise `_require_portal_read_auth` et `_noc_json_response` du contrat NOC issu de PR #36. Sans `AIOPS_PORTAL_READ_TOKEN` valide : `401` ou `503` avant lecture de configuration, réponse non cachable.
- Le navigateur efface le jeton immédiatement après lecture du champ, n'utilise pas de stockage persistant, vérifie les enveloppes/états/URL, ignore les réponses tardives après effacement et n'ouvre jamais automatiquement un lien.
- Les liens sont **externes, sans proxy** et non attestés : `CONFIGURED_UNVERIFIED / UNKNOWN`. Aucune preuve de disponibilité ou d'autorisation LIVE.
- Le bootstrap Core/Twin et les commandes DEMO/Copilot historiques restent publics sur `main` : converger PR #74/#57/#70 avant exposition réseau.

## Qualification

Tests HTTP TestClient dans `tests/test_portal_navigation_auth.py`, inclus dans `.github/workflows/quality.yml`. Tests in-process avec un upstream volontairement défaillant, **pas** des tests d'intégration conteneurs. n8n/Thruk/Grafana/GLPI, auth réelle des services, Debian et captures LIVE : `NOT_TESTED`.

Rollback source : revert de la PR sur branche après revue, sans modification de runtime ni de configuration des services.
