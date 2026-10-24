# GLPI — Sauvegarde physique à froid réalisée (2026-10-22)

Résultats communiqués par l'opérateur SRV-DEB-05 :
- Conteneurs `aiops2-rebuild-glpi` et `aiops2-rebuild-glpi-db` arrêtés avant l'archive.
- Copie du datadir par `docker cp "$DB:/var/lib/mysql/." - | gzip -1`.
- Archive : `/home/aiops/recovery/glpi-mariadb/glpi-mariadb-cold-20261022-181301.tar.gz`.
- Contrôle `gzip -t`, `tar -tzf` et SHA-256 : PASS ; `GLPI_COLD_BACKUP=PASS`.
- Le trap a exécuté les commandes `docker start` sur MariaDB puis GLPI; les statuts, la santé MariaDB et l'accessibilité SQL ne sont **pas encore vérifiés après reprise**.
- Sauvegarde SQL historique du 19 octobre : test gzip PASS. Authentification SQL MariaDB `glpi` et `root` (env, socket) en erreur 1045 avant arrêt.
- Prochaine étape : vérifier les deux conteneurs en lecture seule puis créer une copie isolée du volume dans un conteneur MariaDB 11.4 sans réseau, sans publication de ports, sans montage du volume original et avec credentials secrets. Ne jamais tenter une récupération `--skip-grant-tables` sur l'instance live ni modifier les tables mysql avant validation et rollback.
- Kit de démonstration ACME (6 CIs, 2 incidents) et Grafana préparés, mais **aucun import réel GLPI** validé.
