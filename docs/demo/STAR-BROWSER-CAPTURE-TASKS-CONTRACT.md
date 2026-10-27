# STAR — Préparation de navigation Chromium, sans accès aux applications

## Objectif
Le plan de captures `star-capture-execution-worklist-v1` contient les identifiants vérifiés par scène, mais pas les URL effectivement révisées par un opérateur. Le module `demo/star_browser_capture_tasks.py` produit maintenant une liste d'instructions navigateur à partir de ce plan, des URL **exactes fournies** pour chaque étape prête, et des trois origines approuvées (n8n, GLPI, Grafana).

## Limites contractuelles
- Refuse une URL manquante, une origine non approuvée, un paramètre de requête, un fragment, un chemin avec `..`, une URL répétée entre scènes et une URL pour une étape sans identifiants.
- Refuse toute affirmation d'exécution navigateur ou de preuve runtime dans le plan.
- Produit des tâches en mode `GET` et `navigation_only=true` ; une requête GET n'est pas nécessairement sans effets de bord : **ne pas exécuter ces tâches contre une production sans revue et autorisation des routes exactes**.
- `browser_executed=false`, `runtime_proof_count=0`, `live_action_authorized=false`. Le module n'ouvre aucune page et ne fabrique aucune capture.
- Les URL des exemples de tests sont des fixtures locales, pas des routes applicatives garanties. La reconstruction des vraies routes nécessitera une revue de la configuration des applications et une qualification isolée.

## Tests
`tests/test_star_browser_capture_tasks.py` : cas partiellement prêt, absence d'URL devinée, origine étrangère, URL attachée à une étape bloquée et réutilisation abusive d'une même URL. Le workflow `STAR screenshot integrity collector` a été étendu pour les compiler et les exécuter.

## Suite
Développer un exécutant Playwright isolé derrière `ReadOnlyRequestPolicy`, avec contrôle des ressources, navigation fail-closed, délai limité, vérification du texte métier et de l'identité de l'exécution avant toute capture. Intégrer les résultats au portail `:17777` seulement après attestation indépendante.
