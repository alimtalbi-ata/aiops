# V2.13.15 — Priorité parallèle intégration CMDB/observabilité/workflows

Le théâtre STAR V2.13.15 a été qualifié en Chromium local par l'opérateur : 10/10 PASS, pas d'erreur JS. Non construit/déployé à ce stade.

L'utilisateur demande parallèlement de compléter rapidement GLPI, créer des incidents démonstratifs, enrichir Grafana et les workflows n8n. Kit source créé:
- `demo/integrations/v21315/acme-fixtures.json`: 6 CI fictifs avec dépendances et 2 incidents simulés;
- `validate_fixture.py`: contrôles locaux standard Python;
- `n8n/acme-incident-demo-dryrun.json`: workflow **inactif** sans écriture externe;
- `grafana/acme-synthetic-observability.json`: dashboard de démarrage (Prometheus up = collecte réelle éventuelle, le reste narratif fictif);
- `README.md`: intégration progressive et règles de sécurité.

**Aucune opération GLPI/n8n/Grafana en exploitation n'a été effectuée**, aucune donnée synthétique ne doit être confondue avec un incident réel. Travaux suivants : schéma CI GLPI 11 identifié sur l'instance en lecture seule, mapping et import idempotent dry-run avec rollback et accord préalable; Grafana datasource vérifié; tests de workflow n8n sur environnement isolé; E2E démontrable. Un seul portail utilisateur 17777, aucune activation LIVE.
