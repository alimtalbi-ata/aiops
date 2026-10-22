# ACME — État des intégrations découvert le 22 octobre 2026

Sortie de l'inventaire en lecture seule exécuté par l'opérateur sur SRV-DEB-05 :

| Conteneur | Image | État |
|---|---|---|
| aiops2-rebuild-grafana | grafana/grafana:13.2.2 | running, healthy (27 h) |
| aiops2-rebuild-glpi | glpi/glpi:11.0.9 | running (51 secondes lors du diagnostic) |
| aiops2-rebuild-n8n | n8nio/n8n:2.40.6 | restarting, exit 1, boucle apparente |
| aiops2-rebuild-glpi-db | mariadb:11.4 | running, healthy (27 h) |

Fixtures locales : AIOPS_DEMO_FIXTURES=PASS, 6 CIs, 2 incidents.

**Priorité P0 : diagnostiquer n8n sans redémarrer ni modifier la plateforme.** Consulter seulement l'état Docker, le nombre de redémarrages et les journaux récents, en retirant toute valeur sensible avant publication. Ne pas importer de workflows n8n tant que le conteneur n'est pas stable. Ne pas tirer de conclusion prématurée sur la cause de l'échec.

Travail parallèle permis : mappings API GLPI/relations CI, plan idempotence et rollback, vérification datasource Grafana en lecture seule, préparation dashboard DEMO, sans écriture en production.

L'unique portail utilisateur reste 17777. Aucun accès historique déverrouillé, aucune remédiation LIVE, aucune fusion automatique.
