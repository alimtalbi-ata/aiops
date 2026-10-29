# P0 NOC/ITSM — raccord de présentation sans attestation (29/10/2026)

**READY_FOR_STABLE=BLOCKED / DEMO_READY terrain=NOT_READY.** Source: issue #186 et branche historique `feat/acme-core-noc-itsm-correlation-20261027`, notamment `app/portal/acme_itsm_correlation.py` et son contrat de ticket revendiqué mais jamais vérifié par GLPI. Ne pas monter directement cet ancien router : ses dépendances `noc_runtime`, `acme_impact_read_model` et `noc_correlation` ne sont pas présentes sur `prep/acme-demo-offline-20261029`.

## Livraison verticale

`app/shared/acme_itsm_evidence_link.py:project_itsm_evidence` réutilise le contrat de projection non attestante et joint en mémoire les snapshots du détail Core `GET /api/runs/{rid}` et du proxy viewer `GET /api/demo-studio/runs/{rid}/ai-ledger`, **à condition qu'ils aient été lus par les lecteurs serveur déjà autorisés**. Le résultat `CORRELATED_UNATTESTED` expose les IDs canoniques Run/Incident/Analysis/Critique/Policy/Evidence. Aucun I/O, jeton, endpoint, montage dans `app/portal/main.py`, requête GLPI ou écriture. Le ticket NOC signé est uniquement `glpi_ticket_claim`, jamais `ticket_id`. Un vrai ticket GLPI reste UNKNOWN tant qu'aucun lecteur GLPI autorisé ne le confirme. `SYNTHETIC_ONLY` n'est pas SOURCE-VERIFIED.

Tests `tests/test_acme_itsm_evidence_link.py`: **12/12 PASS locaux** en Python stdlib sur fichiers construits dans un environnement isolé (fixtures, pas de Core/GLPI). Tests négatifs: données absentes, mauvais Run, LIVE, tenant/runtime flags, Evidence vide/hash, références Critique/Policy croisées, ticket NOC non signé/synthétique. **CI quality.yml du commit, Debian, 401 HTTP, tenant A/B, GLPI API, E2E, rollback et applied.sha: NOT_TESTED** au moment de la rédaction.

## Intégration 2/5 et 5/5

Ne pas monter ni rendre visible avant qu'un lecteur serveur autorisé fournisse deux snapshots du même Run, en respectant RBAC viewer et jeton Core uniquement serveur. Ne pas inventer `tenant_acl_qualified=true` ou `runtime_attested=true`. Si aucun ticket GLPI authentifié n'est disponible, afficher `Ticket GLPI : UNKNOWN (claim NOC non vérifié)`. La route `/demo-studio` du portail appartient à 2/5 ; aucun fichier UI n'a été modifié. Recette 5/5 reste seul responsable de l'assemblage et de la promotion stable. La candidate #185 et le poller Debian portal-only ne transportent pas automatiquement ce module. Aucun LIVE ni déploiement.
