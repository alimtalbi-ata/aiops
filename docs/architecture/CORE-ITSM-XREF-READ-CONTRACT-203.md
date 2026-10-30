# Core ITSM ↔ Incident/Run authoritative read contract — #203

**Status: proposed main-based design and offline mock projection only. NOT_INSTALLED.** This document does not describe a deployed Core endpoint or a verified GLPI ticket. Architecture and reuse register: PR #195. Central journal: #186. Tracking blocker: #203.

## Inspected sources / reuse

- main at 27deb9b1a66faf27df8d69b137a63451f7649d80: app/portal/noc_correlation.py reads GET /api/noc/runs/{rid} with internal Bearer and signed NOC HMAC, but returns MATCHED_UNATTESTED, not tenant-qualified ITSM linkage. app/core/main.py has no tenant-scoped ITSM xref GET. shared/tenant_scope.py rejects unqualified tenant claims; it is not an IdP.
- #197 HEAD 571943714ef3d3a30bf2205a8d94aa918db01e6e (base main): Evidence known_at UTC preflight is injectable, not a GLPI connector or Evidence attestation; selectively reuse before upstream GET.
- #198 HEAD 8f48b1b5a94960ce4ddcc1ca35bf206302543e94 (base main): Run locator needs protected GET /api/noc/runs/{rid}/evidence-refs, missing from main. Its synthetic-only result is not tenant or runtime proof.
- #192 HEAD 8488e64c718ba887cb9b1e4a3b0161c8a435232f (stacked base fix/ingest-stage-terminal-state): GLPI client GET /apirest.php/initSession, GET /Ticket/{ticket_id}, GET /search/Ticket, GET /killSession with App-Token + GLPI user/session token. Session CONNECTED does not establish tenant/GLPI entity ACL or ticket↔Run mapping. ASCII ticket IDs, GET-only, redirect and ACL hardening remain required.
- #193 HEAD e8f05d8c50045f4256e89ad0776424f4dad5bb61 (stacked on #192): RUN-* in GLPI title/content plus Core Run existence is wrongly promoted to LINKED. This MUST NOT be reused or passed as a Copilot run binding without Core authoritative tenant-scoped VERIFIED readback.
- #203 is an **issue**, not a PR: it has no Git SHA/base. It owns the missing Core authoritative contract.

## Authority, time and cardinalities (target; not runtime observed)

| Identity / relation | Source and owner | Cardinality | Freshness and provenance | Current status |
|---|---|---|---|---|
| tenant → principal | IdP + Core ACL | tenant 1:N principals | authenticated scope, ACL version | UNKNOWN |
| incident → run | Core lifecycle, Bearer read | incident 1:N runs; run 1 incident | lifecycle event known_at | synthetic only, tenant UNKNOWN |
| run ↔ GLPI ticket | Core immutable xref, GLPI ticket API | run 0:N historical links; ticket 0:N historical links, at most one active per tenant/instance/ticket/role | GLPI observed_at, Core known_at, source_event_id, association_id, mapping_version | UNKNOWN |
| ticket ↔ CI | GLPI CMDB/entity ACL | 0:N ↔ 0:N | GLPI observed_at, GLPI entity scope | UNKNOWN |
| run ↔ Evidence | Core events + append-only Evidence | run 0:N refs | Evidence observed_at, known_at, hash, source | UNKNOWN |
| AI ledger ↔ Evidence | Core analysis/critique refs, Evidence service | analysis 0:N refs | source/provenance/hash/freshness | UNKNOWN |

observed_at means source observation time; known_at means when Core learned/recorded the fact. Never treat a seed, a title, a 200 GET, or a synthetic reference as a verified relationship.

## Proposed API — NOT PRESENT ON MAIN

GET /api/tenants/{tenant_id}/itsm/glpi/{glpi_instance_id}/tickets/{ticket_id}/xref

- Core server must authenticate a trusted service principal with itsm:xref:read and enforce tenant ownership for GLPI instance/entity/ticket, incident, run and CI **before** returning mapping. The tenant parameter must be checked against server-authenticated scope, never client-supplied authority.
- Response schema aiops.core-itsm-xref-read.v1: status VERIFIED|UNKNOWN|CONFLICT|STALE|UNAUTHORIZED, tenant_id, glpi_instance_id, ticket_id, incident_id, run_id, source_system=GLPI, source_event_id, association_id, mapping_version, verification_method=AUTHENTICATED_ID_READBACK, tenant_acl_qualified, glpi_ticket_readback_verified, core_run_readback_verified, observed_at, known_at, provenance=AUTHENTICATED_SOURCE_API.
- Trusted client must pin Core origin, use scoped Bearer, GET-only/no redirects, bound response size, reject duplicate JSON keys, not log secrets; the injected CoreRead authenticated/tenant_acl_checked flags are **client-side assertions**, not fields to trust from JSON.
- The proposed shared.core_itsm_xref_read.resolve_ticket_run validator exposes run_id, incident_id and ticket_id **only** on strict VERIFIED Core readback. No GLPI call, Copilot call, DB access or network transport exists in this module. CI and Evidence IDs are always empty/null.
- Link status and connector health are distinct: VERIFIED is not CONNECTED. Missing Core callback => connection_state NOT_INSTALLED and link_status UNKNOWN. 401/403 => UNAUTHORIZED; 404 => UNKNOWN; 5xx/exception => UNAVAILABLE; stale/conflict => STALE/CONFLICT, no IDs. Invalid tenant, ID or Evidence UTC short-circuits before any Core GET.
- Five-minute freshness is a conservative offline fixture policy for mapping observed_at/known_at, subject to Core/GLPI owner approval; it is not a validated production SLA.

A future trusted Core write path, not part of this PR, must record immutable/audited tenant+instance+ticket+incident/run+CI associations, actor/service identity, GLPI source readback, observed_at/known_at, mapping version, idempotency key and supersession. Core owns the xref; GLPI owns ticket/CMDB; Evidence stays append-only. No direct DB bypass or GLPI writes.

## Required handoff

Core owner / #203: inspect actual schema, implement audited xref persistence, tenant ACL and GET with ephemeral DB integration; reconcile duplicates, supersession, conflicts and stale links. 3/5: reuse and harden #192 GET client with explicitly approved test credentials only. 2/5: never pass a text-extracted run_id to Copilot or create proposal without Core VERIFIED. 5/5: selectively consolidate main-based work and qualify exact integrated SHA/CI plus approved T1/T3 authenticated reads; do not merge #192/#193 stacked branches wholesale.

**Qualification:** offline contract/mocks and Python compile only. No Core xref endpoint, GLPI credentials, authenticated tenant ACL, real Evidence, CI or ticket link was available. Runtime relation state remains UNKNOWN with ticket_id=null, run_id=null, evidence_id=null, verified_evidence_ids=[]. No LIVE, GLPI write, SSH/sudo, deployment or merge.
