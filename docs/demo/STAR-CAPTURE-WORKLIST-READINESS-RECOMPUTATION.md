# STAR — Recalcul de l'éligibilité des captures

## Problème
Une liste d'exécution pouvait se fier au champ `capture_ready_for_attempt` d'un manifeste d'identités. En cas de modification ou de corruption de ce champ, une étape pouvait apparaître prête sans posséder les identifiants nécessaires.

## Correction
`demo/star_capture_execution_worklist.py` recalcule désormais les identifiants manquants à partir du contrat par scène `_REQUIRED`. Le module refuse tout statut de préparation incohérent, la suppression d'un identifiant non répercutée dans `missing_identifiers`, une liste `required_identifiers` modifiée, un identifiant mal formé et un `run_id` divergent entre les scènes. Il continue à exiger un rapport historique sans preuve runtime.

## Tests
`tests/test_star_capture_execution_worklist.py` couvre trois nouvelles régressions : statut prêt falsifié, identifiant effacé et run_id divergent. Ces tests sont inclus dans le workflow STAR screenshot integrity collector. Vérifier les résultats CI pour le dernier SHA avant qualification.

Cette amélioration intervient **hors ligne** ; aucun navigateur ni service GLPI, n8n, Grafana ou Debian n'a été sollicité. Un statut prêt autorise uniquement la tentative contrôlée de capture, jamais la remédiation LIVE ni l'affirmation d'une preuve authentifiée.
