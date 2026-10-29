# AIOps2 — État des sauvegardes

Date : 2026-10-29T22:28:38+01:00

## Exports locaux vérifiés

- PostgreSQL AIOps2 : export présent, gzip valide
- PostgreSQL Temporal : export présent, gzip valide
- MariaDB GLPI principale : export présent, gzip valide

## Encore à sauvegarder

- MariaDB GLPI historique : échec d'authentification ou de droits
- Volume GLPI fichiers
- Volume n8n
- Autres volumes persistants nécessaires

## Limites

Les sauvegardes sont locales.
Les restaurations ne sont pas encore testées.
Les dumps SQL ne sont pas encore publiés sur GitHub.
