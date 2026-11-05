# AIOps2 — reprise architecturale FS.364 → livraison E2E

Date de référence : 2026-11-06. Source : observations terminal communiquées dans la conversation courante, inventaire des cinq tâches ChatGPT existantes et arborescence du dépôt GitHub. Les autres conversations ne sont pas intégralement accessibles ici ; ne pas prétendre les avoir toutes relues. **Ce document est un état de reprise, pas une preuve de déploiement.**

## Contexte et vérité d'exécution

Hôte Debian : SRV-DEB-05, utilisateur aiops. Déploiement Docker Compose avec Core `aiops2-rebuild-core`, Portal `aiops2-rebuild-portal`, Worker `aiops2-rebuild-worker`, GLPI `aiops2-rebuild-glpi` et laboratoire isolé `aiops2-fs-lab`. Le dépôt `alimtalbi-ata/aiops` contient app/core, app/portal, app/worker, app/policy, app/twin, docs, integration, tests, scripts et compose.yml. **Le code GitHub main n'est pas présumé identique aux images actives sur Debian.** Préserver le checkout dirty, les overlays Compose et les autres démonstrations.

Le conteneur lab possède `/fs-lab` sur tmpfs 12 MiB ; mesure exécutée le 2026-11-06 : 11264 KiB utilisés / 12288 KiB, 1024 KiB libres, **92 %**. Fichier dominant `/fs-lab/aiops2-demo-fill.bin`, 11 534 336 octets. `du` et `ls` confirmés ; aucun descripteur ouvert correspondant observé lors du scan ponctuel. BusyBox ne supporte pas `find -printf`. Le Core n'a **pas** ce montage ; toute commande `df /fs-lab` dans Core est incorrecte. Il s'agit d'un **incident mesuré réellement dans un laboratoire intentionnellement saturé**, et non d'une panne de production.

GLPI : ticket **147** créé via API, type incident=1, statut nouveau=1, référence `AIOPS2-REAL-FS-20261106`. FS.364 a créé et relu cinq suivis natifs IDs **25–29** : métriques, fichier, processus/descripteurs, dépendances/critic, Policy/HITL. Ticket historique **146** préservé ; approbation native `TicketValidation/3` ACCEPTED ne concerne **que le diagnostic historique** et **n'autorise aucune suppression**. Aucun fichier supprimé, aucune remédiation exécutée. Les rapports Core historiques RUN-8ADA4220B525EC4C, RUN-7CBFA35B5120DB02 et RUN-C70AB93D7A83B9B3 sont BLOCKED ; le dernier état ne prouve pas de nouveau RUN relié à 147. Un RUN insuffisant RUN-B78AEF53C2E71C6D est également BLOCKED.

Observabilité précédemment confirmée : Worker exporte `aiops2_fs_lab_used_percent` à 92 et `AIOps2FilesystemUsageHigh` FIRING dans Prometheus ; **revérifier en direct avant d'en déduire l'état actuel**. Pipeline Worker arrêté à DGX_CRITIC, étapes suivantes PENDING. Les résultats DEMO ne doivent jamais être présentés comme LIVE.

## Objectif produit

Deux boutons Portal `/fs-real`, sans login UI (authentification backend maintenue) :
1. Saturation lab réelle → alerte Prometheus → incident/runs/évidences corrélés → df/du/ls via bridge read-only → Analyst/Critic → Policy BLOCKED ou HITL authentique → remédiation *uniquement après autorisation spécifique et vérifiée* → mesure après intervention → rapport GLPI.
2. Données insuffisantes → questions humaines GLPI/Copilot/Temporal → attente/reprise conditionnée par réponses réelles ; aucune résolution inventée.

## Architecture cible / contrats

Corrélation durable `alert_fingerprint -> incident_id -> run_id -> evidence_id -> glpi_ticket_id`, avec idempotency key et horodatages. Stockage durable côté Core ou DB ; ne pas se baser sur un texte libre GLPI comme unique source. Endpoint interne sécurisé de liaison au ticket existant 147, **sans création d'un second ticket** ; distinguer `GET/read`, `POST/create`, `sync`, `resume` et effets. Ne jamais réutiliser l'ancienne validation 146 pour 147.

Bridge fs-lab limité à l'inspection `df/du/ls` ; toute action mutante doit exiger une approbation native ciblant **ticket 147 + run + action + chemin + taille/empreinte + expiration + validateur distinct**, contrôlée côté backend juste avant exécution ; journaliser preuve de décision, résultat et mesure post-action. Aucun job cron, automatisation ChatGPT, test ou agent ne doit exécuter suppression/truncate/remplissage, accepter une validation ou simuler un statut RESOLVED.

## Plan de livraison, preuves et tests

P0 : auditer diff entre GitHub main, patchs hôte et images actives ; établir contrat d'API de création RUN et liaison ticket147 ; vérifier Prometheus actuel. Livrer documentation des écarts, pas d'auto-déploiement.

P1 : implémenter flux `alert -> run/evidence -> ticket147` avec idempotence, et traces de chaque étape réelle. Tests négatifs : alert absent, Core inaccessible, double clic, réexécution cron, GLPI indisponible, mauvais ticket, DEMO/LIVE mismatch.

P2 : Analyst/Critic/Policy sur observations lab réelles ; publier en GLPI uniquement les événements réellement enregistrés. BLOCKED explicite si dépendances, rétention, autorisation ou confiance insuffisantes.

P3 : HITL natif spécifique 147, attente et reprise Temporal contrôlées ; tests de rejet, expiration, mauvaise identité, mauvaise action, double approbation, refus. **Aucun déblocage sur la base du ticket146.**

P4 : deuxième bouton « données insuffisantes » avec questions/réponses humaines et reprise, pas de faux succès.

P5 : qualification end-to-end avec un seul `run_id` cohérent entre Prometheus/Core/Worker/Temporal/Portal/GLPI. Définition de DONE : preuves des transitions, UI lisible, refus sûr, tests automatisés, validation humaine réelle et démonstration de vérification post-intervention seulement après approbation spécifique. Séparer systématiquement CODE / CI / HÔTE / EXÉCUTÉ / BLOQUÉ.

## Orchestration

Cinq tâches ChatGPT existantes, horaires Europe/Paris : Portal, Core, Twin, Worker, Intégration, actuellement horaires. Réorienter leurs prompts sur cette reprise, garder leur cadence, privilégier PRs, tests et livrables concrets ; ne pas supposer qu'elles ont accès à Debian. La tâche d'intégration coordonne et produit un état factuel. Un cron Debian distinct peut relever **en lecture seule** la mesure du lab et l'état des conteneurs dans un journal local avec verrou `flock`, sans secrets et sans mutation GLPI. Installation du cron à faire **sur Debian**, non depuis ce connecteur GitHub.

## Règles non négociables

Pas de secrets dans GitHub/logs. Pas de contournement OIDC/ACL/Policy/STOP_AUTO. Pas de suppression avant HITL ciblé vérifié. Pas de fausse approbation, de faux RUN ou de faux RESOLVED. Préserver GLPI 146 et 147, éviter doublons, respecter le mode DEMO. Tout changement sur hôte exige des preuves locales de déploiement et des tests.
