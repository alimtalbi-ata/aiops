# 2026-10-28 17:51 CET — P0 ACME cibles de checkpoints canoniques

## Vérification préalable
- HEAD `main` : `7659cc32b573e0bb847221b9d1dc5081039a0f3e` ; HEAD PR draft [#133](https://github.com/alimtalbi-ata/aiops/pull/133) : `1f430030d434136c2597c87aa82dce1c39998e4d` avant écriture, revérifiés via GitHub.
- PR ouvertes examinées, notamment #127 (entreprise 60 CI, mapping séparé), #128 (Evidence), #120 (GLPI HTTP), #36 (source de fixture v1) ; journaux récents Explore/Story, NOC, continuité et décision log relus. Travail poursuivi **uniquement** sur la branche propriétaire `feat/p0-acme-scenario-contract-20261028-1153`, sans merge massif.
- Micro-lot : verrouiller les neuf couples cue/service/view/required_state pour éviter qu'une projection accepte des cibles trompeuses. Publication additive de `events[].expected_state` (cible fictive, non état observé).

## Fichiers et contrat
- `app/portal/acme_scenario_contract.py` : mapping exact des neuf checkpoints, rejet fail-closed de service/vue/état falsifiés, champ `expected_state`.
- `tests/test_acme_scenario_contract.py` : tests négatifs de falsification et suppression de required_state, réponse 503 UNKNOWN sans fuite, assertions de déterminisme et statut MISSING.
- `docs/demo/ACME-SCENARIO-CONTRACT-V1.md` : tableau canonique et exemple JSON ; avis aux consommateurs Explore/Story/NOC/ITSM.
- Ce journal. Commits : `3625486514b4a1cfe03b4e84516ad09ebe923496` (code/tests/docs/journal initial) puis `8f4b13255e80740b950cb7e58416e4eceec60e0b` (correction syntaxique Python). `main` et l'ancien HEAD ci-dessus sont les bases attestées.

## Validation et limites
- [GitHub Actions quality #40730317325](https://github.com/alimtalbi-ata/aiops/actions/runs/40730317325), SHA `36254865` : **FAILURE** ; erreur de syntaxe due à deux séquences littérales `\\n` introduites dans le patch Python. Corrigées immédiatement dans le même micro-lot, sans masquer cet échec.
- [GitHub Actions quality #40730344907](https://github.com/alimtalbi-ata/aiops/actions/runs/40730344907), SHA exact **`8f4b13255e80740b950cb7e58416e4eceec60e0b`** : **completed/success**, vérifié via GitHub. Les 3 jobs `policy-and-static`, `core-postgres-noc-real-integration`, `grafana-real-integration` sont terminés avec conclusion **success**. Étapes confirmées : compilation Python, tests ACME scénario (y compris négatifs), tests impact, audit statique, Compose, vrais HTTP Core/PostgreSQL et Grafana. Ces jobs d'intégration ne qualifient pas ACME/GLPI/Temporal.
- Le commit de mise à jour de ce journal déclenchera un nouveau run PR ; **son résultat reste NOT_VERIFIED** jusqu'à consultation du SHA final.
- **NOT_TESTED** : Core/Temporal/GLPI sur ce scénario, navigateur réel, capture authentifiée, ACL tenant runtime, LLM, Debian, vidéo finale. Les tests contractuels sont locaux/ASGI ; jobs Grafana et Core/PostgreSQL ne prouvent pas l'intégration ACME.
- DEMO / `SIMULATED_TARGET` uniquement ; `expected_state` ne prouve ni événement runtime, ni ticket GLPI, ni approbation HITL. Aucune écriture backend, commande LIVE, secret de production, SSH ou déploiement.

## Risques et prochain lot
- Risque de mauvaise interprétation de `expected_state` par les consommateurs : UI doit le libeller « attendu » et conserver `MISSING` visible. Coordination publiée sur [PR #127](https://github.com/alimtalbi-ata/aiops/pull/127#issuecomment-6475187227).
- Prochain micro-lot : exposer l'ID événement et l'état attendu dans le panneau Explore/Story sans changer les IDs, puis qualification navigateur isolé et preuves de capture traçables.
