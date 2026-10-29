# AIOps2 — Sauvegarde de reconstruction

Date : 2026-10-29T22:29:16+01:00

## Bases sauvegardées
- PostgreSQL AIOps2
- PostgreSQL Temporal
- MariaDB GLPI principale

## Volumes archivés
- GLPI fichiers
- n8n données

## À compléter
- MariaDB GLPI historique
- Validation de restauration isolée
- Inventaire des autres volumes requis
- Publication des données synthétiques après vérification

## Limites
Les archives GLPI et n8n ont été réalisées à chaud.
Leur cohérence applicative n'est pas encore démontrée.
Les données ne sont pas encore publiées sur GitHub.
