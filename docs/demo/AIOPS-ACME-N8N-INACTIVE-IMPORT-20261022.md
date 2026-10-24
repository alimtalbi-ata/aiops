# ACME n8n — Import désactivé réussi (2026-10-22)

Résultats fournis par l'opérateur sur SRV-DEB-05 :
- Fichier import corrigé avec un identifiant racine; permissions dans le conteneur corrigées par `chown node:node`, `chmod 600`.
- `ACME_IMPORT_FILE_READABLE=PASS`.
- Commande `n8n import:workflow --input=... --projectId=wWbgOGJQjaWCmkHq --activeState=false` : `Successfully imported 1 workflow`, `ACME_N8N_IMPORT_COMMAND=PASS`.
- PostgreSQL `workflow_entity` : `1ba56aaabaf9400b|ACME DEMO — Incident dry-run (NO external writes)|f`.
- Avertissement Postgres 16 / support compatibilité seulement, sans échec de l'import.
- Aucune exécution de workflow ni activation vérifiée, uniquement import et indicateur active=false.
- Prochaine étape lecture seule : joindre `shared_workflow`, `project`, `workflow_entity`, vérifier `active=false`, relations et nœuds; tests Code gate sans déclencher de webhook. Prévenir toute exposition, garder Compose secret réseau privés.
