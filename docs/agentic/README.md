# Agentic Engineering — intégration AIOps2 V28

Source : archive utilisateur `projet-agentic.zip` (2026-11-05). Le squelette Claude Code est fourni comme **outillage de développement optionnel**, pas comme moteur d'exécution AIOps2.

## Périmètre
- Processus : cadrer → modéliser → tranche verticale → revue → évaluation.
- Rôles : analyste métier, architecte, développeur, testeur, sécurité, reviewer.
- Les modèles de spécification, ADR, tâches, hooks et évaluations du paquet source restent des références ; ils ne sont pas installés à la racine du dépôt.
- Ne pas remplacer le `CLAUDE.md`, les `.claude/settings.json` ou les workflows existants sans revue explicite.

## Règles AIOps2 prioritaires
1. Aucune exécution LIVE, GLPI write, modification Docker ou changement de schéma via l'outillage agentique sans autorisation humaine indépendante.
2. Respecter OIDC, ACL tenant+acteur, STOP_AUTO, Core HTTP 503 fail-closed, anti-rejeu, approbation et Evidence PG16.
3. Les démos filesystem ne modifient que des états logiques synthétiques, avec run-id, rollback et reçu SHA256.
4. Le cron Debian bidirectionnel existant n'est pas remplacé. Le checkout Debian avec modifications non commitées ne doit pas être écrasé.
5. Aucun secret, `.env`, log privé, jeton, reçu non expurgé ou capture hôte n'est publié.
6. Distinguer CODE, CI, MERGED, HOST_EXECUTED, EVIDENCE_PUBLISHED et E2E. Ne pas déclarer un GO sur une simulation.

## Déploiement
Intégration **source-only** en branche isolée. Aucun hook, agent Claude, cron, test automatique, exécuteur ou déploiement hôte n'est activé par cette PR.
Les commandes du paquet original sont des exemples et doivent être adaptées à la stack avant activation. Le hook `tests-avant-stop.sh` a un TEST_CMD vide dans la source : il ne valide donc rien par défaut.

## Première tranche métier
Utiliser le parcours filesystem synthétique #422/#423/#428 comme cas pilote : spec → décision → exécution synthétique → vérification → rollback → attestation. La preuve hôte reste obligatoire.
