# V2.13.60 — Replay STAR lié à une empreinte de captures indépendante

## Objectif métier
Empêcher qu'un replay ACME SAN P1 / Payments P2 affiche comme cohérent un jeu de neuf captures remplacé, partiellement absent ou différent du jeu préalablement retenu. Le portail unique :17777 reste le seul point d'entrée utilisateur; ce changement n'ajoute ni route, ni port, ni déploiement.

## Patrimoine réutilisé, pas réécrit
- `demo/star_browser_manifest_gate.py`: validation des neuf checkpoints, identités canoniques, PNG réels en octets, SHA-256, ordre et chronologie; produit `capture_set_sha256` en mode strict.
- `demo/star_checkpoint_reconciliation.py`: contrôle indépendant des références run/correlation/event.
- `demo/star_snapshot_choreography.py`: ordre normatif des neuf étapes.
- `demo/star_capture_set_replay_gate.py`: nouveau contrôle **de comparaison** avec l'empreinte retenue indépendamment; ne remplace aucun module existant.
- Le patrimoine F20.13 Playwright GLPI :8080 / n8n :5678 / Grafana :3000 est documenté comme historique, **pas restauré à partir de fragments tronqués**. Aucun fichier de session ni capture d'authentification n'est importé.

## HLD / flux de confiance
1. Une source canonique indépendante fournit `run_id`, `correlation_id` et les neuf `event_ref`. Le manifeste ne peut pas s'auto-déclarer source canonique.
2. Le collecteur offline vérifie les neuf manifestes et les octets PNG, calcule `capture_set_sha256` (liaison déterministe).
3. Une source **distincte** et préalablement retenue (registre/replay approuvé pour comparaison) fournit `pinned_sha256`.
4. `verify_pinned_replay_captures(root, canonical, filenames, pinned_sha256)` exige l'égalité exacte du digest; refus de jeu incomplet, mixte, malformé ou modifié.
5. Les captures de fixture ne passent qu'avec `allow_synthetic_fixture=True`; les captures opérateur restent `OPERATOR_BROWSER_UNREVIEWED`.

## LLD / interface et sécurité
- Entrées : chemin du dossier local, mapping canonique, noms de manifestes, SHA-256 indépendant sur 64 caractères hexadécimaux minuscules, booléen explicite de fixture.
- Sortie : contrat `star-pinned-replay-captures/v1`, SHA-256, run_id, provenance et `replay_integrity_checked=True`. Les flags `runtime_authenticated`, `business_validated`, `human_approval_authenticated`, `live_action_authorized` restent **False**.
- Refus `ValueError` sur digest absent/invalide, divergence, neuf étapes incomplètes, provenance mixte ou fixture non autorisée.
- Comparaison par `hmac.compare_digest`. Aucun appel HTTP, Chromium, base de données, GLPI, n8n, Grafana, Temporal, DGX, ticket ou remédiation LIVE.
- **Limite importante** : une empreinte calculée depuis les mêmes manifestes n'est **pas** un ancrage indépendant. Ce contrôle ne prouve pas l'authenticité du runtime, la page GLPI affichée, le ticket, l'approbation HITL ou le résultat métier.

## Qualification
- Local isolé : `python -m unittest discover -s tests -p 'test_star_capture_set_replay_gate.py' -v` (tests unitaires à dépendance simulée).
- GitHub Actions : workflow `STAR browser manifest bridge (offline)`, incluant les tests d'intégration des neuf PNG synthétiques et les tests de réconciliation.
- Cas négatifs : pin altéré, timestamp modifié, PNG changé, jeu partiel, provenance mixte, fixture non autorisée, faux drapeau d'attestation.
- Qualification navigateur Chromium et portail Debian : **non démontrées par ce module**.

## Rollback
Revert des commits du nouveau module, tests, documentation et modification du workflow sur la branche draft uniquement. Les modules historiques et le portail déployé restent inchangés. Aucun merge automatique.

## Prochaine intégration
Relier un `pinned_sha256` conservé indépendamment par le replay à la lecture du storyboard du portail, uniquement après revue des interfaces et tests E2E isolés. Rechercher le code source F20.13 original complet avant réutilisation; ne jamais promouvoir les journaux ou fragments comme sources exécutables.
