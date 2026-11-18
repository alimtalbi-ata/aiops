# INT08B — proposed independent authorities v1 (offline only)
Baseline 13aabde7f05632a36679b96e11334add406d62ac, PR818 frozen. This is not an approved wire or authentication protocol. No credentials, endpoint calls or server modifications.
## Registry
All roles tenant ACME-TEST only; tenant entitlement must be derived server-side from verified workload identity + durable Run binding, never browser input. Proposed transport authenticated TLS HTTP read-only except Temporal native read-only gRPC; proposed automated workload identities via short-lived workload certificates and audience-bound tokens issued by a trusted workload identity provider, no operator secrets. Distinct server principals and least-privilege reader scopes. Issuer/trust roots, namespace, service DNS, audience, token lifetime, rotation and revocation need architect/security approval. Revoke certificate/key/entitlement or registry revision; fail closed on unknown revocation or unavailable verifier. No numeric production freshness threshold approved; explicit policy per source, fixture 60 s only.
| Logical role | Owner | Proposed technical principal | Proposed audience / scope | Observation timestamp | Envelope payload |
|---|---|---|---|---|---|
| core | Core | workload:core-prepared | core / read:prepared | committed snapshot time | V4 Core envelope, Run identity, manifest |
| twin | Twin | workload:twin | twin / read:approval | fact/approval issuance | V4 Twin envelope, impact, ASCII nonce |
| policy | Policy | workload:policy | policy / read:decision | persisted decision time | V4 Policy envelope |
| history | Temporal | workload:history-reader | temporal / read:history | immutable history event time | receipt and history digest |
| postcheck | independent evidence owner (TBD) | workload:postcheck | postcheck / read:verification | independent probe time | V4 history digest and verification |
| terminal | Core distinct read principal | workload:core-terminal | core / read:terminal | committed terminal snapshot time | V4 terminal record, postcheck digest |
Core and terminal share owner, not an independent database; separate read identities are proposed, not demonstrated. Collector identity separate from producers. Collection clock belongs to reader, never substitutes source observation. Strict UTC, server event clock and collector clock synchronization/uncertainty need approval.
## Static capability inventory
Source inspection only, no live checks. All listed paths refer to baseline.
| Need | Existing route or code | Status | Gap |
|---|---|---|---|
| Core Run canonical | GET /api/runs/{rid}, app/core/main.py:263 | EXISTS_BUT_INSUFFICIENT | global read, no tenant auth, no immutable manifest |
| Core tenant Run | app/core/portal_tenant_runs.py read_runs_for_bearer | EXISTS_BUT_INSUFFICIENT | helper not endpoint; no snapshot/attempt contract |
| Core synthetic read | GET /api/noc/runs/{rid}, :300 | EXISTS_BUT_INSUFFICIENT | internal bearer, synthetic only, explicitly no runtime authentication |
| Twin topology/impact | GET /api/twin/graph, /api/twin/impact/{node_id}, /api/twin/at | EXISTS_BUT_INSUFFICIENT | global reads, no tenant or approval binding |
| Twin persisted approval | no route in app/twin/main.py | MISSING | independent versioned read required |
| Policy persisted decision | POST /api/policy/check, app/policy/main.py:85 | EXISTS_BUT_INSUFFICIENT | evaluates request, not independent persisted decision |
| Core stored Policy | GET /api/noc/runs/{rid}/policy-status | EXISTS_BUT_INSUFFICIENT | not Policy authority |
| Temporal history | GET /api/execution/{run_id}/inspect, app/worker/main.py:137 | EXISTS_BUT_INSUFFICIENT | admin bearer, start args only, explicitly unattested |
| Independent postcheck | no matching route in audited Core/Twin/Policy/Worker mains | MISSING | owner/contract unresolved |
| Terminal double read | GET /api/runs/{rid} | EXISTS_BUT_INSUFFICIENT | no immutable terminal snapshot or linked postcheck |
| Worker expected /api/sandbox/acme/e2e/{attempt_id} | client contract app/worker/acme_simulated_hitl.py | MISSING | no matching handlers in audited service mains |
| Deployed ingress, actual TLS, IAM, Temporal namespace ACL | not inspected live | NOT_VERIFIED | runtime access prohibited |
No EXISTS_AND_COMPATIBLE authority found. MISSING limited to audited modules, not deployment-wide proof.
## Python seam and schemas
New additive module portal.acme_independent_authorities. AuthorityReader(request:dict)->tuple[bytes,dict|None]; inspect_authority_batch(expected,intent,registry,requests,observations,*,as_of_utc). C owns invocation; B never calls readers here. Existing B V4 and C INT07 signatures unchanged. READ_SEQUENCE core,twin,policy,core,history,postcheck,terminal,terminal. Receipt is payload of history and remains existing seven-ID schema. C must continue existing collect_prepared/qualify_continuity/collect checks, not substitute this admission seam. No automatic adapter or runtime permission.
Registry schema aiops.int08.authority-registry.v1, authorities map exact six roles. Example entry (all names fixtures, no usable credentials):
```json
{"source_id":"core-001","principal":"fixture:core","audience":"fixture-audience:core","scope":"read:core","tenant_id":"ACME-TEST","max_age_seconds":60,"revocation_state":"ACTIVE"}
```
Request example (identity abbreviated here; actual eight keys required):
```json
{"role":"core","challenge":"CHALLENGE-001","identity":{"tenant_id":"ACME-TEST","incident_id":"INC-001","impact_incident_id":"INC-002","run_id":"RUN-001","attempt_id":"ACME-SIM-001","proposal_id":"PROP-001","ticket_id":"SIM-GLPI-001","approval_id":"SIM-APP-001"}}
```
Envelope exact fields: schema aiops.int08.authority-envelope.v1, role, source_id, classification STORY_OFFLINE, identity (eight), snapshot_id,parent_snapshot_id,version,observed_at,content,content_sha256. Separate metadata fields classification OFFLINE_TEST_METADATA,principal,audience,scope,tenant_id,challenge,envelope_sha256,collected_at. Digest canonical B JSON, no signature. Complete executable examples in tests. Source identity metadata must ultimately come from verified transport, not payload. Here it is deliberately injected and never trusted. Core-generated Run required in future: expected Run must come from a tenant-authorized Core lookup, never generated by C/UI; current fixture comparison cannot prove origin.
## Protocol and B/C dependencies
B: registry schema, identity binding, digest and time preflight; existing V4 validates parent/version/nonce ASCII verbatim, receipt/history/postcheck links and terminal equality. C: separate acquisition, one-use challenges, double reads, reader failure handling, true workflow history and postcheck, existing V4 invocation. Core first observation and second must match immutable payload, terminal observations likewise; distinct collection metadata/challenge. PREPARED -> receipt in history -> postcheck -> terminal strictly increasing observation times. C must retain INT07 auxiliary prepared/receipt/manifest/independent observers; mapping new outer envelopes into existing C roles needs joint decision and tests. New seam deliberately does not validate payload business semantics or create V4 input.
## Refusal and risk
BLOCK missing evidence, freshness policy, revoked/unknown source, stale observation, nominal fixture. REJECT source/principal/audience/scope/tenant/run/snapshot contradiction, replay challenge, digest or envelope binding, future time, version, changed double read, synthetic claimed runtime. See code for exact reason strings. Every return UNBOUND/UNKNOWN and all authority flags false. In-batch replay only; no durable replay store, no real cryptographic verification, no proof of Core origin, no cross-process registry authenticity. Metadata can be forged coherently. Scope equality is a fixture rule not a real IAM parser. No live endpoint verified. Future design needs server-issued challenge/channel binding (or signed response with request nonce), durable replay handling, trust anchor and key rotation, tenant ACL enforcement, immutable snapshot persistence, independent probe ownership and approved source clocks/policies. Request arbitration before any server/API/auth/DB change. 
## Integration allowlist
app/portal/acme_independent_authorities.py; tests/test_acme_independent_authorities.py; docs/contracts/int08b-independent-authorities.md. Dedicated workflow qualification only, not product merge. Existing four baseline files unchanged.
