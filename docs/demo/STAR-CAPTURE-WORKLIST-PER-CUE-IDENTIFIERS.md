# STAR — Transmission des identifiants à la campagne Chromium

## Problème fonctionnel
Le plan `star-capture-execution-worklist-v1` conservait le statut de préparation de chaque étape, mais perdait les identifiants réellement vérifiés. Un collecteur navigateur ne pouvait donc pas retrouver l'exécution n8n ou le ticket GLPI correspondant à une scène sans relire et interpréter un deuxième manifeste.

## Correction
`demo/star_capture_execution_worklist.py` émet désormais `steps[].capture_identifiers` : seulement les identifiants attendus pour la scène d'après `_REQUIRED` (run_id, execution_id spécifique à n8n, ticket_id, alert_id ou approval_id). Ces valeurs sont validées avant inclusion ; aucune URL, clé de session ou credential n'est exporté. Les scènes incomplètes conservent seulement les identifiants existants et restent `MISSING_IDENTIFIERS`. Les identifiants n'ont pas été confirmés contre les services réels : `runtime_proof_count=0` et `live_action_authorized=false`.

## Tests et prochaines étapes
Le test `test_validated_business_ids_are_available_to_read_only_capture` vérifie la propagation de deux ID d'exécution n8n distincts, d'un ticket GLPI, et l'absence d'un identifiant manquant. Le test fait partie du workflow STAR screenshot integrity collector. Inspecter la CI du commit exact.

La prochaine étape est d'utiliser `capture_identifiers` pour sélectionner les vrais écrans Chromium en lecture seule, sur un environnement isolé, vérifier run/exécution/ticket/alerte dans la page et générer des preuves horodatées reliées au portail `17777`. Pas de changement des conteneurs Debian ni d'écriture métier.
