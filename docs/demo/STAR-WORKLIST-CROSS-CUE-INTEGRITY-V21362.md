# STAR — intégrité des plans de capture inter-checkpoints (V2.13.62)

## Contexte et patrimoine

Les audits Playwright F20.13 d'octobre 2026 décrivent des captures GLPI, n8n et Grafana. Le plan de lacunes `star-legacy-capture-gap-plan-v1` n'est **pas** une preuve d'exécution. Le plan d'identité `star-capture-identity-plan-v1` peut être exporté, puis altéré avant sa jonction avec le plan historique. Les sources Playwright historiques originales complètes ne sont pas restaurées par cette modification.

## Besoin métier

Avant toute tentative de capture en lecture seule pour la cinématique SAN P1 → Payments P2, chaque checkpoint doit conserver sa propre identité applicative. Une exécution n8n unique ne doit pas être utilisée pour prouver deux étapes distinctes (corrélation, enrichissement, analyse, simulation). Les anciens PNG ne remplacent pas les neuf captures à réaliser.

## HLD / flux

`plan_capture_identity` + `build_gap_plan` → sérialisation potentiellement non fiable → `join_capture_plans` (barrière de sécurité) → plan de travail `READY_FOR_READ_ONLY_CAPTURE` ou `MISSING_IDENTIFIERS` → collecteur Chromium séparé, jamais lancé ici.

## LLD / garde-fous

- Refuser `identity.read_only != true`.
- Refuser `historical.historical_byte_integrity_is_not_runtime_attestation != true` et `historical.live_remediation_authorized != false`.
- Recalculer le nombre d'étapes prêtes à partir des identifiants requis et comparer à `identity.capture_attempt_ready_count` (entier strict, booléens interdits).
- Refuser tout `execution_id` n8n réutilisé dans deux checkpoints.
- Préserver `runtime_proof_count=0` et `live_action_authorized=false` dans la sortie.

## Qualification et limites

`python -m unittest discover -s tests -p 'test_star_capture_execution_worklist.py' -v` ; CI existante `.github/workflows/star-capture-evidence.yml` inclut déjà ces tests et s'active sur leurs fichiers. Les cas négatifs couvrent la duplication d'exécution, le nombre de captures prêtes falsifié et les indicateurs de confiance hérités. Ce contrôle ne vérifie ni le DOM, ni l'authentification, ni les octets PNG, ni les événements sources. Aucune preuve métier n'est déclarée.

## Rollback

Sur la branche draft, revert des commits modifiant `demo/star_capture_execution_worklist.py`, `tests/test_star_capture_execution_worklist.py` et ce document. Ne pas fusionner ni déployer tant que la CI de la branche n'est pas réussie. Aucun changement de configuration Debian, port, ticket, base ou service n'est requis.
