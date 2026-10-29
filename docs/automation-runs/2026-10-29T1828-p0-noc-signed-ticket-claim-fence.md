# P0 NOC/ITSM — refus de faux ticket signé (29/10/2026)

**DEMO_READY terrain=NOT_READY / READY_FOR_STABLE=BLOCKED.** Directive #186 et contrat historique `feat/acme-core-noc-itsm-correlation-20261027:app/portal/acme_itsm_correlation.py` relus. Aucun changement Portal, Docker, DB, stable ni LIVE.

## Bloqueur précis corrigé sur la branche prep existante

Le raccord `app/shared/acme_itsm_evidence_link.py` pouvait afficher `glpi_ticket_claim` depuis un dictionnaire arbitraire qui affirmait simplement `source_authentication=HMAC_SHA256_VERIFIED`, sans vérifier le schéma/provenance de l'enveloppe NOC existante. Ce n'était jamais un `ticket_id` connecté, mais le libellé « signed NOC » était trop permissif pour une vidéo de démo.

Correctif minimal : exiger `schema=aiops.noc-runtime-envelope.v1`, `source_mode=ALLOWLISTED_HMAC_SIGNED_READ_MODEL`, `provenance=AUTHENTICATED_SOURCE_PAYLOAD_NOT_RUNTIME_ATTESTATION`, `production_qualified=false` et `ticket_provenance=UPSTREAM_SIGNED_CLAIM` en plus des garde-fous existants. Ces champs sont émis par le lecteur historique `portal.noc_runtime._project_signed_payload` après vérification HMAC. **La fonction pure ne vérifie pas elle-même de signature** : elle doit recevoir un snapshot issu du lecteur serveur autorisé, jamais une entrée navigateur.

Commits : code `c7d3d32f5d97857e10e8c24766a12b7cc70d39dd`, tests `6e6c980f33a5d8232ed949a49ef6541ff21cfa77`. Git blob des deux fichiers testés et poussés : code `759fb9fe6a6feb780b74b45b3d36d90ff67c5582`, tests `cbd752a4284cdf95f5049ebcb39b6170c41229f0`.

**Tests réellement exécutés en environnement local éphémère :** `python3 -m unittest discover -s tests -p test_acme_itsm_evidence_link.py -v` → **13/13 PASS**, `python3 -m py_compile` → PASS. Test négatif nouveau : schéma, source_mode, provenance, qualification production ou provenance du ticket forgés → `glpi_ticket_claim=null` et `ticket_id=null`. Tests sur fixtures Python, **pas** sur Core/GLPI HTTP. `quality.yml` sur ces commits : **NOT_RUN** (branche prep non incluse dans push CI) ; Debian, tenant A/B, GLPI réel, `applied.sha`, E2E et rollback : **NOT_TESTED**.

## Contrat et handoff 2/5 / 5/5

La sortie reste `aiops.acme-itsm-evidence-link.v1`, `CORRELATED_UNATTESTED` ou `UNKNOWN`, `SYNTHETIC_ONLY`, `ticket_id=null`, `tenant_acl_qualified=false`, `runtime_attested=false`, `effect_applied=false`. Aucun endpoint nouveau ni mutation. Écran cible existant : `/demo-studio/run/{rid}` et `/evidence`, uniquement après lecture Core+Ledger autorisée par le serveur et montage décidé par 2/5/5/5.

Candidate unique : PR #185, ne pas pousser dessus depuis 3/5 ; intégrer ces **deux fichiers** seulement si le raccord est réellement utilisé dans la démo. Sinon garder `Ticket GLPI : UNKNOWN` et prioriser le parcours visible déjà existant. Le poller Debian portal-only ne transporte pas ce module. **READY_FOR_STABLE=BLOCKED** tant que CI du SHA intégré, packaging, rollback, smoke et `applied.sha` ne sont pas attestés.
