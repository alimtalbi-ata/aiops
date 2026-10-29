# 2026-10-29 18:20 — Policy/HITL 4/5 : résultat SIMULATE présentable, sans effet

**READY_FOR_STABLE=BLOCKED / DEMO_READY=NOT_ATTESTED.** Issue #186 consultée ; main `27deb9b1a66faf27df8d69b137a63451f7649d80`. Aucun accès Debian/Docker, aucune mutation stable ou LIVE, aucune nouvelle PR.

## Code livré sur prep/acme-demo-offline-20261029

- `app/shared/acme_policy_demo_result.py` : `present_demo_policy_result(receipt)`, présentation pure du reçu existant produit par `build_run_remediation_receipt` → `project_remediation` → `evaluate_simulation`. Commit `145f90dfb10ceb09b5dd159b1e10e5b6c7d66b4d`.
- `tests/test_acme_policy_demo_result.py` : 9 tests (SIMULATE/BLOCKED, LIVE, faux claims Core/Evidence, gate incohérente, cible, rollback, non-mutation). Commit `1876340ea1220f1273e0ab73745e2d7a25df563d`.
- **Contrat 2/5 :** `aiops.acme-policy-demo-result.v1` avec `classification`, `source`, `run_id`, `scenario_id`, `option{recipe_id,target_ci,scope}`, `policy{decision,source,core_policy_verified,reason}`, `human{status,authenticated_runtime,glpi_ticket_verified}`, `before_after{before,after_hypothesis,observed,provenance}`, `rollback{status,executed,projected_only}`, `risks[]`, `evidence{ids,receipt_digest,core_verified,tenant_acl_qualified,runtime_attested}`, `effect_applied`, `persisted`.
- SIMULATE signifie uniquement gate locale no-effect ; `core_policy_verified=false`. `APPROVAL_FIXTURE_ONLY` n'est pas une authentification GLPI. Après hypothétique non observé, rollback non exécuté, IDs offline non Core, causalité SAN→Payments UNKNOWN. Ne pas injecter ce résultat comme un Run Core.

## Tests réellement exécutés

Local éphémère : `python3 -m unittest discover -s tests -p test_acme_policy_demo_result.py -v` **9/9 PASS**, `python3 -m compileall -q app/shared/acme_policy_demo_result.py tests/test_acme_policy_demo_result.py` PASS. Blobs GitHub identiques aux fichiers testés (`a49c470daed9e32824c3fc80003b1893fdde5763`, `d6de71ebc0ac8c9b0ca04bf32f3665e7a45c99c9`).

**NOT_TESTED :** générateur réel du reçu dans checkout complet, suites complètes, quality.yml sur SHA prep, HTTP Core/Evidence, tenant/RBAC, Temporal/HITL/GLPI, SAN→Payments, portail Debian, applied.sha et rollback. 44/44 Debian historiques limités à `0d7f2ac`. Candidate #185 HEAD observé `6eb5b23e55c72c827a433e2c5788b501ebdaaf4f`, 4 workflows SUCCESS mais ne qualifie pas ces deux fichiers.

**Handoff 5/5 :** reprendre ces deux fichiers dans la candidate unique, tester l'intégration avec le vrai receipt et quality.yml sur le SHA intégré, vérifier packaging déployeur et smoke read-only/rollback avant toute promotion. 2/5 peut lire le contrat dans les écrans existants, jamais comme une preuve runtime.
