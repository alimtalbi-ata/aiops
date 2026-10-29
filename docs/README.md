# AIOps2 — Kit de reconstruction

Date du checkpoint : 2026-10-29

## Contenu

- sources/active : code actif AIOps2
- sources/historical : ancien dépôt
- sources/recovered : modules historiques récupérés
- sources/candidate : Portal candidat non déployé
- scripts : scripts de diagnostic et de qualification
- git-history : historique Git exporté
- inventory : inventaire Docker et empreintes SHA-256
- db-exports : emplacement réservé aux exports synthétiques

## État vérifié

- Core / Worker : fonctionnement fail-closed précédemment validé
- GLPI Reader : 24 tests unitaires réussis
- ITSM : 23 tests réussis, 1 échec
- HITL : 56 tests réussis, 11 échecs
- Console : 11 tests réussis, 4 échecs
- Portal candidat : tests bloqués par glpi_reader absent
- n8n : workflow ACME dry-run confirmé
- GLPI REST réel et création de tickets : non validés
- Bot historique : récupération non terminée

## Reconstruction

1. Restaurer le dépôt et consulter les historiques Git.
2. Vérifier Dockerfiles, Compose, variables d'environnement et volumes.
3. Recréer les bases à partir des migrations et fixtures.
4. Restaurer les exports de données synthétiques si disponibles.
5. Construire les images et démarrer les services en environnement isolé.
6. Exécuter les tests GLPI, ITSM, HITL, Console, Core et Worker.
7. Vérifier RBAC, isolation tenant et politique fail-closed.

ATTENTION : ce kit n'est pas encore une restauration intégrale validée.
Les dumps de bases et les contenus des volumes doivent être exportés
et testés séparément.
