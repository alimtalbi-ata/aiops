# ACME — Implémentation incrémentale du laboratoire de remédiation (2026-10-29)

## Portée de cette livraison GitHub
Branche : `prep/acme-demo-offline-20261029`.

**Réutilisation ciblée**, sans cherry-pick de l'ancien Policy/Portal :
- `app/shared/remediation_lab.py` : module historique repris **sans modification fonctionnelle** de `feat/p0-hitl-remediation-lab-simulator-20261027-2024`.
- `config/remediation/recipes.v1.json` : catalogue historique des 8 recettes `SIMULATOR_ONLY`.
- `tests/test_remediation_lab.py` : tests historiques réutilisés.
- `app/shared/acme_remediation_projection.py` : nouvelle projection **purement en mémoire** après passage du garde-fou historique.
- `tests/test_acme_remediation_projection.py` : nouveaux tests succès, échec, rollback projeté, LIVE bloqué, refus d'approbation, préconditions, cible et déterminisme.

## Contrat exact de la projection
`project_remediation(proposal, decision, preconditions, before, *, outcome='SUCCESS', now=None)`

Entrées : proposition à recette autorisée, décision HITL de fixture, préconditions explicites, état synthétique `{target_ci,health,service_available}`, scénario SUCCESS/FAILURE. Sortie : `gate`, `before`, `after`, `rollback`, provenance `WHAT_IF_FIXTURE_NOT_OBSERVED`, `effect_applied=False`, `postchecks=NOT_RUN`, `SIMULATED_SUCCESS` / `SIMULATED_FAILURE` / `BLOCKED`.

**Attention** : l'état après n'est PAS une mesure ; `HEALTHY` est une hypothèse synthétique pour le scénario SUCCESS, jamais une preuve de récupération du service. L'état d'échec et le rollback sont eux aussi des projections. L'approbation `authenticated=True` du laboratoire est une fixture, **pas** une approbation réelle. Le moteur ne lance aucun script, commande, HTTP, DB ou effet. Le statut Policy `SIMULATE` ne dispense pas de lier et qualifier les contrats d'autorisation entre services.

## Commandes de qualification offline (sur Debian, pas de Docker)
Après synchronisation GitHub :
```bash
cd /home/aiops/aiops2-p0-consolidation
set -e
python3 -m unittest discover -s tests -p 'test_remediation_lab.py' -v
python3 -m unittest discover -s tests -p 'test_acme_remediation_projection.py' -v
python3 -m py_compile app/shared/remediation_lab.py app/shared/acme_remediation_projection.py tests/test_remediation_lab.py tests/test_acme_remediation_projection.py
python3 tools/acme_offline_source_preflight.py
git diff --check
git status --short
```

**Qualification au moment du commit : NON EXÉCUTÉE sur Debian.** Le code est publié, pas encore validé par un environnement Python de l'opérateur. Ne pas confondre publication GitHub et tests réussis.

## Prochain incrément d'intégration (non livré)
1. Comparer les contrats Core de propositions et de Policy avec les fixtures du laboratoire ; ne jamais convertir automatiquement un `PASS/SIMULATE` en approbation HITL.
2. Associer `run_id`, `scenario_id`, `evidence_ids`, hash de proposition et résultat de projection dans un artefact synthétique persistant, avec contrôle tenant et lecture portail.
3. Vérifier les scénarios SAN/Payments (le catalogue actuel contient un redémarrage Linux ERP, pas de recette SAN Fabric A). Ajouter une recette SAN simulée **seulement après** examen des branches historiques et de la topologie.
4. Tester erreurs Analyst/Critic, stale evidence, échec/rollback, GLPI et UI dans un staging Compose neuf. Aucune modification des conteneurs `aiops2-rebuild-*` sans accord et plan de retour arrière.


## Incrément suivant — liaison offline run/evidence (29 octobre)

**Livré en source** : `app/shared/acme_remediation_receipt.py` et `tests/test_acme_remediation_receipt.py`. La fonction `build_run_remediation_receipt(run,proposal,decision,preconditions,before,evidence_ids,outcome,now)` crée une enveloppe déterministe liant `run_id`, `scenario_id`, mode synthétique, hash de proposition, identifiants de preuve triés et résultat de projection. Elle rejette LIVE, un run non synthétique, une incohérence de mode, des identifiants mal formés et des preuves vides/dupliquées ; elle conserve le refus HITL/Policy du laboratoire.

**Séparation cruciale** : cette enveloppe n'interroge **pas** Core ni Evidence. `core_run_verified=False`, `evidence_verified=False`, `persisted=False`, `classification=SYNTHETIC_UNVERIFIED`. Le digest est une empreinte de liaison, **pas** une signature d'authenticité. Elle ne publie pas d'API et n'effectue aucun appel réseau, SQL ou Docker. Le prochain incrément doit qualifier les références et le scope auprès de Core/Evidence et définir une persistance/read-model sûre avant exposition au portail.

### Qualification à demander sur Debian

```bash
python3 -m unittest discover -s tests -p 'test_acme_remediation_receipt.py' -v
python3 -m unittest discover -s tests -p 'test_remediation_lab.py' -v
python3 -m unittest discover -s tests -p 'test_acme_remediation_projection.py' -v
python3 -m py_compile app/shared/acme_remediation_receipt.py
```

**Statut au commit :** code publié, tests du nouveau module **non encore exécutés** sur Debian. Les 18 tests précédents étaient PASS sur `8901ca9`. Aucun déploiement autorisé par cette livraison.
