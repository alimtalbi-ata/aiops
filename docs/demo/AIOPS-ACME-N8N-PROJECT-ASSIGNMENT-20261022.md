# ACME — Vérification du rattachement workflow n8n (2026-10-22)

L'opérateur a confirmé via jointure PostgreSQL `workflow_entity`, `shared_workflow`, `project` :
`1ba56aaabaf9400b|ACME DEMO — Incident dry-run (NO external writes)|f|wWbgOGJQjaWCmkHq|Unnamed Project`.

Import ACME V2.13.15 réussi; projet personnel `wWbgOGJQjaWCmkHq`; `active=false`; aucun appel webhook ou exécution réelle certifiée. Le workflow n'est pas à activer en production sans test isolé du gate `SIMULATED_TARGET`, refus des demandes non conformes et revue de provenance.

Prochaine action utile : analyse hors réseau du code du nœud Code sur quelques entrées synthétiques/hostiles; contrôle lecture seule de l'état GLPI, de sa base, des réseaux et des CIs préexistants avant import; qualification du datasource Grafana sans modification. Portail unique 17777, n8n secret override privé.
