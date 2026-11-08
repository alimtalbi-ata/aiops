# AIOps2 — cadence coordonnée (Europe/Paris), 2026-11-08

## ChatGPT (cinq automations actives)
- H:00 — Intégration: gate, coordination, rapport horaire
- H:12 — Core: normalisation, corrélation, topologie, contrats et IA
- H:24 — Worker: Temporal, Policy/HITL, exécution et preuves
- H:36 — Twin: scénarios de qualification, isolation
- H:48 — Portal: vues NOC, parcours utilisateur, tests E2E

Chacune a une récurrence HOURLY et un DTSTART décalé de 12 minutes, Europe/Paris. Les tâches ne sont pas elles-mêmes exécutées toutes les 12 minutes. Les commits et l'état Debian doivent être relus à chaque passage, pas supposés.

## Cron Debian constaté par sortie utilisateur
- Chaque minute: `/home/aiops/aiops2-auto-deploy/poll.sh` (flock poll.lock)
- Chaque minute: `/home/aiops/.local/bin/aiops-debian-reporter` (flock cron.lock)
- Chaque minute: `/home/aiops/.local/bin/aiops-publish-report` (flock publish.lock)
- Toutes les 10 min: `/home/aiops/aiops2-operations/fs-watch.sh`
- H:17: `/home/aiops/aiops2-audit-tools/platform_hourly.sh`

## Règles de coordination
1. Un commit GitHub ne signifie pas un déploiement Debian. Exiger reçu et empreinte installée.
2. Ne pas créer de cron concurrent. Réutiliser les trois mécanismes à la minute.
3. Le cron minute est confirmé présent, mais le contenu de poll.sh, les branches consommées et les contrôles de sécurité ne sont pas encore vérifiés dans ce dépôt. Aucun déploiement applicatif automatique n'est donc déclaré prêt.
4. Chaque tâche publie un état CODE / CI / DEBIAN / E2E, tests et handoff vers le rôle suivant.
5. Le rapport de H:00 récapitule la dernière heure; ne pas prétendre qu'il est instantané si les tâches n'ont pas fini.
6. Préserver les données, les autorisations HITL, l'idempotence ITSM et les rollback.
