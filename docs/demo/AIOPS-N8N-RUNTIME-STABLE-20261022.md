# Validation n8n après réparation — 2026-10-22

Résultats exécutés par l'opérateur sur SRV-DEB-05 :

- `STATUS=running`
- `RESTARTS=0`
- `N8N_HTTP=200` pour `127.0.0.1:5678/healthz`
- `SELECT COUNT(*) FROM workflow_entity` retourne `0`
- Vérifications précédentes : DNS et TCP PostgreSQL PASS, trois réseaux control/data/integration attachés, volume n8n persistant conservé, configuration de chiffrement privée et sauvegardes présentes.
- La réparation du runtime est validée par ces contrôles, pas l'exécution d'un workflow de bout en bout. Aucune importation/activation n'a encore eu lieu.
- Next: valider JSON workflow n8n via parser local, adapter au cas échéant le schéma d'import n8n 2.40.6, importer d'abord **désactivé** dans l'instance ACME, puis tester webhook uniquement après vérification des accès, du gate SIMULATED_TARGET et de l'absence de side effects. Attention à préserver secrets, aucune exposition de nouveau port, sans perturber GLPI/Grafana/portal.
