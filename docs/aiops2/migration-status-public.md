# AIOPS2 — État de préparation de la migration

> Document public expurgé. Il ne contient ni identifiants, ni valeurs d'environnement, ni données métier, ni sauvegardes.

## Objectif

Préparer la consolidation progressive des services AIOPS2 dans une pile Docker Compose unique, en préservant les données, les volumes, les réseaux et les paramètres d'exécution existants.

## Avancement

- Inventaire de référence établi pour 21 services candidats.
- Brouillons Compose préparés et validés syntaxiquement ; **non approuvés pour le déploiement**.
- Sauvegardes locales de préparation réalisées pour les bases de données, les volumes applicatifs et les montages de configuration.
- Restaurations SQL effectuées dans des environnements temporaires isolés pour PostgreSQL AIOPS2, PostgreSQL Temporal et MariaDB GLPI.
- Contrôles de structure réussis pour les trois restaurations ; cela ne constitue **pas** une vérification complète des données.
- Copie privée des fichiers d'environnement et références de reprise créée et relue.
- Runbook préparatoire de reprise rédigé localement.

## Limites et conditions préalables

- Les sauvegardes sont locales ; aucune copie hors serveur des archives sensibles n'est confirmée.
- Les sauvegardes ont été effectuées à chaud ; une sauvegarde cohérente au point de bascule reste nécessaire.
- Les données métier et la restauration intégrale des volumes ne sont pas encore validées.
- La reprise des identifiants et privilèges administratifs doit être vérifiée.
- Le plan de bascule service par service et le retour arrière doivent être approuvés explicitement.
- Les conteneurs historiques ne seront pas automatiquement adoptés par un nouveau projet Compose.

## Sécurité de publication

Ce dépôt public peut accueillir des documents expurgés, des scripts génériques et des configurations nettoyées. Il ne doit **jamais** recevoir les archives SQL ou de volumes, les fichiers d'environnement privés, les secrets, les jetons, les clés ou les copies brutes de configurations.

## Statut

**Bascule en production : NON AUTORISÉE.**

Suivi opérationnel : [issue #555](https://github.com/alimtalbi-ata/aiops/issues/555).
