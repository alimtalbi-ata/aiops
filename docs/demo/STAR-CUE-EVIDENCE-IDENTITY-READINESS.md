# STAR — Identifiants indispensables pour la capture métier

L'absence des identifiants réels de suivi était un obstacle à la réutilisation de la cinématique F20.13. Le module `demo/star_capture_identity_plan.py` construit, sans réseau ni écriture, un plan de préparation pour chacune des neuf étapes de `demo.star_snapshot_choreography.CUES`.

| Étape | Application | Identifiants indispensables |
|---|---|---|
| detect | Grafana | run_id, alert_id |
| correlate | n8n | run_id, execution_id |
| enrich | n8n | run_id, execution_id |
| analyze | n8n | run_id, execution_id |
| ticket | GLPI | run_id, ticket_id |
| approve | GLPI | run_id, ticket_id, approval_id |
| simulate | n8n | run_id, execution_id |
| verify | Grafana | run_id, alert_id |
| close | GLPI | run_id, ticket_id |

`capture_ready_for_attempt=true` signifie uniquement que les identifiants nécessaires ont été *fournis* ; cela n'atteste ni la réalité, ni la concordance des événements, ni la session Chromium. Aucun identifiant n'est fabriqué lorsqu'il manque. `runtime_proof_count` reste zéro en l'absence d'une qualification authentifiée indépendante. La simulation n'autorise jamais une remédiation LIVE.

Tests automatisés : absence totale d'identifiants, jeu complet, approbation manquante et identifiants invalides. Le workflow `STAR screenshot integrity collector` comprend leur exécution ; son résultat doit être vérifié au SHA courant.

Prochaine étape : relier les identifiants de la stack V1/V2 depuis les manifests d'exécution réellement capturés, avant de créer des preuves PNG horodatées et d'afficher les neuf vues dans le portail :17777. Aucun accès au serveur Debian ni modification des applications pour ce développement.
