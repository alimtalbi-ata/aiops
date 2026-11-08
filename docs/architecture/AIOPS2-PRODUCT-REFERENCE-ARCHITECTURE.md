# AIOps2 — architecture produit de référence (proposition, non déployée)

## Finalité
AIOps2 est un produit AIOps installable chez un client ITIL 4, avec les outils, droits et topologies déjà en place. Le Digital Twin est un banc de test interchangeable, non une dépendance produit.

## Plans
- **Source plane**: connecteurs supervision, observabilité, CMDB, cloud, stockage, réseau, ITSM; lecture seule par défaut; découverte des capacités et permissions.
- **Normalization plane**: schéma canonique versionné (SourceEvent, Resource, BusinessService, Dependency, Incident, Run, Evidence, Analysis, Decision, ActionIntent, ExternalReference); identités internes immuables, références externes multi-systèmes, provenance et fraîcheur.
- **Decision plane**: Core (cycle de vie/corrélation), graphe d'impact, intelligence Analyst/RAG/Critic, Policy/HITL; séparation diagnostic/notification/remédiation.
- **Execution plane**: Temporal (workflow durable) et Worker (actions autorisées); action binding, idempotence, fencing, compensation, vérification et refus fail-closed.
- **Integration plane**: ITSM bidirectionnel avec lookup-before-create, outbox, readback, reconciliation, conflict handling; jamais de création à partir de la seule absence d'une ligne de xref.
- **Evidence and operations plane**: audit append-only, traces run_id/incident_id/action_id, portail NOC, métriques de valeur, RBAC/secrets/retention.
- **Qualification plane**: Digital Twin entreprise, scénarios SAN/FS/réseau/applicatif, défauts et refus, contrat de connecteurs identique à celui des clients.

## Contrats à stabiliser avant implémentation
1. EventEnvelope: schema_version, tenant_id, source_system, source_event_id, observed_at, received_at, correlation_id, payload_ref, evidence_ref.
2. IncidentIdentity: incident_id, external_refs[] (system, kind, id, verification, verified_at), fingerprint, business_service_refs[], state.
3. DecisionRecord: run_id, evidence_ids[], critic_decision, policy_decision_id, action_digest, policy_revision, decision_at.
4. ActionIntent: action_id, run_id, target, parameters_digest, preconditions, approval_binding, idempotency_key, expiry, dry_run.
5. ITSM reconciliation: lookup, match-confidence, readback, conflict state, last_seen, outbox status, no duplicate creation.

These are proposed contracts; compare with Debian live APIs/DB and existing GitHub PRs before migration. No automatic data migration.

## Boundaries and invariants
- Internal AIOps2 service ports: 810–817; external application ports: four digits; GLPI container 80 / host 8080, PostgreSQL 5432, Temporal 7233 are infrastructure exceptions.
- Debian runtime is the operational reference until exact image digests, configs and live routes are reconciled.
- GitHub PR or CI success != deployed state != functional E2E success.
- No merge, cron modification, restart, Docker cleanup, ticket POST, HITL approval or remediation without explicit change approval.
- Read-only observability and ITSM tracking must not imply authorization for infrastructure changes.
- Tenant/customer isolation, least privilege and auditable failure modes are mandatory for client deployment.

## Qualification criteria
An E2E receipt must link source event -> resource/service -> incident -> run -> evidence -> analysis/critic -> policy/HITL -> Temporal/Worker (if applicable) -> ITSM external reference/readback -> audit. Missing steps are UNVERIFIED or NOT_APPLICABLE with justification, never fabricated PASS.
