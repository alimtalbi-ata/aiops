# 2026-10-28 17:51 CET — P0 ACME cibles de checkpoints canoniques

## Vérification préalable
- HEAD `main` : `7659cc32b573e0bb847221b9d1dc5081039a0f3e` ; HEAD PR draft [#133](https://github.com/alimtalbi-ata/aiops/pull/133) : `1f430030d434136c2597c87aa82dce1c39998e4d` avant écriture, revérifiés via GitHub.
- PR ouvertes examinées, notamment #127 (entreprise 60 CI, mapping séparé), #128 (Evidence), #120 (GLPI HTTP), #36 (source de fixture v1) ; journaux récents Explore/Story, NOC, continuité et décision log relus. Travail poursuivi **uniquement** sur la branche propriétaire `feat/p0-acme-scenario-contract-20261028-1153`, sans merge massif.
- Micro-lot : verrouiller les neuf couples cue/service/view/required_state pour éviter qu'une projection accepte des cibles trompeuses. Publication additive de `events[].expected_state` (cible fictive, non état observé).

## Fichiers et contrat
- `app/portal/acme_scenario_contract.py` : mapping exact des neuf checkpoints, rejet fail-closed de service/vue/état falsifiés, champ `expected_state`.
- `tests/test_acme_scenario_contract.py` : tests négatifs de falsification et suppression de required_state, réponse 503 UNKNOWN sans fuite, assertions de déterminisme et statut MISSING.
- `docs/demo/ACME-SCENARIO-CONTRACT-V1.md` : tableau canonique et exemple JSON ; avis aux consommateurs Explore/Story/NOC/ITSM.
- Ce journal. Commit SHA : consulter l'historique de la PR #133 ; `main` et l'ancien HEAD ci-dessus sont les bases attestées.

## Validation et limites
- `.github/workflows/quality.yml` existant : déjà déclenché automatiquement sur la PR #133 ; vérifier le run sur **le nouveau SHA exact** avant de déclarer PASS. CI URL et statut à compléter après exécution ; aucun PASS anticipé.
- **NOT_TESTED** : Core/Temporal/GLPI sur ce scénario, navigateur réel, capture authentifiée, ACL tenant runtime, LLM, Debian, vidéo finale. Les tests contractuels sont locaux/ASGI ; jobs Grafana et Core/PostgreSQL ne prouvent pas l'intégration ACME.
- DEMO / `SIMULATED_TARGET` uniquement ; `expected_state` ne prouve ni événement runtime, ni ticket GLPI, ni approbation HITL. Aucune écriture backend, commande LIVE, secret de production, SSH ou déploiement.

## Risques et prochain lot
- Risque de mauvaise interprétation de `expected_state` par les consommateurs : UI doit le libeller « attendu » et conserver `MISSING` visible.
- Prochain micro-lot : exposer l'ID événement et l'état attendu dans le panneau Explore/Story sans changer les IDs, puis qualification navigateur isolé et preuves de capture traçables.
