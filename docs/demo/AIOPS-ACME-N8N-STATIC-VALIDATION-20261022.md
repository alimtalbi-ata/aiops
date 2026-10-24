# ACME — Qualification statique du workflow n8n (22 octobre 2026)

Résultat opérateur :
- `ACME_N8N_WORKFLOW_VALID=PASS`
- `NODES=3`
- `ACTIVE=False`
- Types présents : webhook, code, respondToWebhook.
- Marqueurs SIMULATED_TARGET et DRY_RUN présents.
- n8n 2.40.6 a été restauré au niveau runtime : HTTP 200, restart count 0, réseaux control/data/integration, PostgreSQL connecté.
- Base au dernier contrôle : 0 workflows, 0 credentials.

**Attention** : vérification statique des types et mentions, pas de preuve d'exécution, ni validation du comportement fail-closed de n8n, ni preuve d'absence de side effects du code à l'exécution. Ne pas activer/publier avant revue et test. Vérifier `n8n import:workflow --help` pour --activeState=false, propriétaires et projet; protéger n8n en conservant les overrides privés de clé et réseaux. Éviter l'import qui écrase des IDs existants, cf documentation n8n; aucune importation encore exécutée.
