# P0 NOC/ITSM — refus des snapshots à scope tenant non qualifié (29/10/2026, 22:20 CET)

**Objet :** correction ciblée de `app/shared/acme_itsm_evidence_link.py`, branche `prep/acme-demo-offline-20261029`, sans modification du portail ni de stable. Référence : issue #186, candidate intégrée #185 (coordination exclusive 5/5).

## Défaut reproductible

Le raccord purement présentation `project_itsm_evidence` pouvait retourner `CORRELATED_UNATTESTED` si un `core_detail.run` ou une Evidence contenait `tenant_id`, `workspace_id` ou `org_id` non autorisé, ou si l'enveloppe NOC contenait une revendication tenant. Ce raccord n'établit aucune ACL tenant : un tel snapshot doit rester `UNKNOWN`. Les lecteurs Portal existants possèdent déjà un garde-fou `reject_unqualified_tenant_scope` ; réutilisé ici, sans nouvel adaptateur.

**Contrat :** `tenant_acl_qualified=false` et `runtime_attested=false` inchangés ; l'unique champ d'enveloppe Ledger `tenant_acl_qualified=false` est exclu du scan récursif (il est validé explicitement juste avant), mais les champs tenant imbriqués et les autres données sont refusés. Aucun nouveau endpoint, token navigateur, appel GLPI, ticket connecté ou effet LIVE. `ticket_id=null` sans lecture authentifiée GLPI.

## Tests et limites

- Reproduction locale isolée sur une reconstruction fonctionnelle du raccord : 4 tests ciblés, **2 FAIL avant** le garde-fou (tenant imbriqué et NOC), **4/4 PASS après** ; `compileall` PASS. **Ce n'est pas une exécution des blobs Git exacts publiés.**
- Trois tests de non-régression ajoutés à `tests/test_acme_itsm_evidence_link.py` : tenant Core/Evidence/Analysis, métadonnées annexes, enveloppe NOC. Tests exacts GitHub de ce nouveau commit : **NOT_RUN** ; CI `quality.yml` : **NOT_RUN** ; Debian/GLPI/HTTP/RBAC tenant A/B/E2E : **NOT_TESTED**.
- Les 16 tests locaux antérieurs ne sont pas une qualification du nouveau SHA.

## Intégration / décision

**READY_FOR_STABLE=BLOCKED ; DEMO_READY Debian=NOT_READY.** Module toujours non monté dans #185. Écran consommateur prévu : `/demo-studio/run/{rid}` et `/evidence`, sous lecteur Portal autorisé et scope non qualifié refusé. Reprendre module et test seulement si 2/5 monte réellement ce résultat, sinon afficher `GLPI UNKNOWN` et ne pas retarder la démo navigable.

**5/5 :** requalifier les tests sur les blobs exacts après intégration, `quality.yml` sur SHA intégré, packaging couvrant `app/shared/`, rollback, `applied.sha` et smoke read-only. Ne pas promouvoir `deploy/aiops2-stable` sans gates. Aucun accès Debian ni action LIVE.
