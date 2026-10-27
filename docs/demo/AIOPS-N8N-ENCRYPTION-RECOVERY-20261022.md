# AIOps — Récupération n8n après divergence de clé (2026-10-22)

Résultats opérateur :
- Base PostgreSQL n8n : 0 workflows et 0 credentials au moment du comptage.
- Volume historique n8n : `aiops2-rebuild-n8n-data`.
- Configuration historique et pg_dump sauvegardés localement sous `/home/aiops/n8n-recovery-20261022-174442`, SHA256 vérifié.
- Override Compose privé avec la clé du volume, non publié, `docker compose config -q` PASS.
- `docker compose ... up -d --no-deps --no-build --force-recreate aiops2-n8n` : conteneur Started.
- `docker inspect` : STATUS=running, RESTARTS=0 ; grep erreurs sur logs --since 2m : aucune sortie; volume après recréation inchangé.
- État : démarrage récupéré; validation de durée, logs complets et disponibilité HTTP encore à effectuer. Ne pas déclarer n8n entièrement qualifié.
- Précaution : l'override contient un secret. Permissions 600, maintien hors repo, conservation dans la procédure d'exploitation. Éviter de lancer Compose sans l'override secret, sinon risque de nouvelle divergence au prochain déploiement.
- Aucun incident synthétique ni workflow n8n importé au moment de ce compte rendu.
