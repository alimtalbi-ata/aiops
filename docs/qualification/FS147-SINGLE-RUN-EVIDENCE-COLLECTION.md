# FS147 — manifeste de collecte E2E (lecture seule)

Statut initial : **NOT_EXECUTED**. Ce modèle n'est ni un reçu réel ni une autorisation de remédiation. Référence : docs/FS364-ARCHITECTURE-REPRISE-2026-11-06.md.

## Identité de l'exécution

- SHA GitHub exact : NOT_VERIFIED
- SHA/image sur Debian : NOT_VERIFIED (ne pas inférer la synchronisation)
- Mode : DEMO / OBSERVE uniquement
- Ticket GLPI : 147 (lecture de la liaison à prouver)
- run_id / incident_id / alert_fingerprint / evidence_id : NOT_OBSERVED
- Horodatage UTC, origine de chaque reçu, acteur authentifié : NOT_OBSERVED

## Chaîne de preuves du **même** RUN

| Étape | Responsable | Reçu exigé | État initial |
|---|---|---|---|
| Mesure lab 92 % et alerte Prometheus FIRING | Twin | Mesure horodatée, labels et fingerprint, isolation /fs-lab hors SAN | NOT_EXECUTED |
| Core | Core | claim durable/idempotent, incident_id, run_id, evidence_id, ticket_id=147 | NOT_EXECUTED |
| Observation read-only df/du/ls | Worker | Trace bridge authentifiée, commandes permises, horodatage, hash de sortie | NOT_EXECUTED |
| Analyst puis Critic | Worker | Deux réponses authentifiées et corrélées au run et aux observations | NOT_EXECUTED |
| Policy | Worker | Décision et motif, mode DEMO, STOP_AUTO, run_id | NOT_EXECUTED |
| GLPI 147 | Intégration | Lecture API authentifiée du ticket et des suivis du même run ; aucune écriture | NOT_EXECUTED |
| HITL natif ciblé | Core | TicketValidation distinct, ticket=147, run/action/path/fingerprint/expiration/validateur ; lecture autoritative | NOT_EXECUTED |
| Reprise sûre Temporal | Core | Décision de reprise/déduplication, fencing et événements du même run ; aucune reprise lancée par cette collecte | NOT_EXECUTED |
| UI E2E | Portal | Trace Chromium et corrélation affichée, aucun RESOLVED sans post-mesure | NOT_EXECUTED |

## Critères fail-closed

Un seul identifiant de RUN à chaque étape ; aucune preuve provenant du ticket 146, d'un autre RUN, d'une fixture, d'une URL non relue ou d'une approbation historique. L'absence de preuve signifie UNKNOWN/NOT_EXECUTED, jamais PASS. La validation du schéma et les tests CI ne prouvent pas l'authenticité d'une URL ni une action réelle. Sans HITL spécifique authentifié : aucune remédiation, aucun signal de reprise, aucun statut RESOLVED. Même avec HITL, une exécution exige une autorisation opérationnelle distincte et un contrôle immédiatement préalable.

## Périmètre parallèle sans confusion

Portal valide FS1113 uniquement sur image candidate reconstruite non-production, via scripts/fs/FS.1113-history-race-candidate-validation.sh : changement rapide 1h/6h/24h, cinq séries API et cinq entrées de légende, absence de réponse périmée, CSP et PortBinding conservés. Ne pas promouvoir fs1097 et ne pas toucher à aiops2-portal:fs1073-csp-candidate. Le parcours « données insuffisantes » vient après la qualification du parcours incident.

## Décision

**NO_GO** tant que tous les reçus réels du même RUN ne sont pas inspectés indépendamment et que les gates CI/host/Portal ne sont pas qualifiés. Aucune opération live ou destructive dans ce document.
