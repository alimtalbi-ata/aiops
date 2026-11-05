# ADR-0001 — Isoler le toolkit agentique Claude Code

Statut : proposé

## Contexte
L'archive `projet-agentic.zip` contient un squelette générique avec `CLAUDE.md`, `.claude/settings.json`, hooks et sous-agents. Le dépôt AIOps2 possède déjà des mécanismes de CI, sécurité, orchestration et déploiement.

## Décision proposée
Conserver l'outillage en documentation optionnelle sous `docs/agentic/`. Ne pas installer les hooks du paquet à la racine ni activer ses permissions par défaut.

## Justification
Éviter la substitution des contrôles de sécurité existants, les collisions de configuration et l'illusion de tests : le hook Stop source possède `TEST_CMD=""`.

## Conséquences
Adoption progressive après revue ; aucun changement d'exécution Debian, aucun déploiement, aucun accès supplémentaire.
