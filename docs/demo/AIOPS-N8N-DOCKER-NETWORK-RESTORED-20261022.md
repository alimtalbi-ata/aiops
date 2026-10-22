# Récupération n8n — DNS et PostgreSQL rétablis (2026-10-22)

Preuves transmises depuis SRV-DEB-05 :
- `docker network connect aiops2-rebuild-data aiops2-rebuild-n8n` exécuté sans erreur.
- `N8N_DNS=PASS` pour `aiops2-postgres`.
- `N8N_POSTGRES_TCP=PASS` pour `aiops2-postgres:5432`.
- Dernier inspect : `STATUS=running RESTARTS=2`.
- Logs : n8n Task Broker ready, JS Task Runner registered, Instance registered; avertissement Python 3 absent pour runner Python interne ; dépréciations de configuration et avertissements Node/pg.
- Le HTTP `/healthz` n'a pas encore été testé depuis ce rattachement; ne pas déclarer l'instance complètement qualifiée.
- Attention : `docker network connect` ne persiste pas après `docker compose ... --force-recreate`. Créer un override réseau sous Compose préservant les réseaux control et integration et ajoutant data, en plus de l'override secret privé. Valider via Compose config sans publier de secrets ni imprimer l'environnement effectif. Recréer uniquement aiops2-n8n après validation. Ne pas modifier PostgreSQL ni les autres services.
- Ensuite seulement, tests DNS/TCP/HTTP et absence de redémarrages sur deux contrôles espacés; workflow ACME reste inactif.
