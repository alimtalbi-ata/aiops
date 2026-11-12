# GLPI actor/tenant authority contract

Status: DESIGN CONTRACT ONLY — no production identity provider is currently implemented.
Related work: PR #520 / issue #519.

## Verified current-state constraints

- `app/core/main.py` authenticates internal Core API calls with `AIOPS_INTERNAL_TOKEN` or the legacy `ADMIN_TOKEN`. This is service-to-service authentication, not an end-user actor identity or tenant ACL.
- `app/shared/tenant_scope.py` explicitly states that no tenant ACL is established by the shared scope fence.
- The Portal's shared read bearer authenticates access to the Portal surface only. It does not establish an actor, tenant, GLPI entity membership, or permission to read a particular Run or ticket.
- Browser-supplied `X-Actor-ID`, `X-Tenant-ID`, `X-GLPI-Entity-ID`, role, organization, or equivalent claims are untrusted and must never grant authority.
- A signed GLPI xref proves the integrity and issuer of an association event; by itself it does not prove that the current requester may access the associated ticket or Run.

## Required server-derived authority

Before mounting either historical ticket-specific Copilot route, the platform must provide a trusted server-side principal resolver. The resolver must validate, at minimum:

1. A cryptographically verified principal from an explicitly trusted identity issuer or authenticated gateway. Validate signature, issuer, audience, expiry, not-before, and key rotation.
2. A stable actor subject and an independently resolved tenant membership. Do not derive tenant from a request body, URL, browser header, ticket text, or the shared Portal bearer.
3. A server-side authorization decision binding actor + tenant + requested action + resource. Deny by default when membership, role, or resource ACL is absent, ambiguous, stale, or unavailable.
4. An explicit mapping from the authorized tenant to permitted GLPI instance/entity scope and Core Run scope. The mapping must be sourced from trusted server configuration or an authoritative ACL service, not caller input.
5. Separate least-privilege service credentials for GLPI and Core readback. Service credentials identify the Portal service to upstreams; they do not replace the end-user authorization decision.
6. An audit record for the decision containing stable actor, tenant, action, resource identifiers, decision, policy version, and correlation ID, without logging bearer secrets.

## Required resource authorization sequence

For a future read-only GLPI-to-Copilot request:

1. Resolve and verify the requester principal server-side.
2. Resolve tenant membership and authorize the requested GLPI ticket read.
3. Read the ticket from the configured GLPI instance using the server-held service credential; validate ticket ID and entity scope.
4. Verify the canonical signed xref event, issuer/audience, expiry, unique active association, and durable nonce replay barrier.
5. Independently authorize the same actor/tenant for the linked Core Run read.
6. Read the Core Run using a separate server-held service credential and compare raw canonical identifiers against the signed association and GLPI readback.
7. Only after all checks succeed may a future, separately reviewed adapter prepare a Copilot context. Any HITL item remains `PROPOSED`; no execution or GLPI write is implied.

Any failed, missing, mismatched, stale, or unavailable dependency returns a generic fail-closed result and performs no Copilot query, HITL proposal, GLPI mutation, or Core mutation.

## Acceptance tests required before route registration

- Missing, invalid, expired, wrong-issuer, wrong-audience, and rotated-key principal credentials are denied.
- Browser-supplied actor, tenant, role, and GLPI entity headers cannot change the resolved principal or authorization result.
- Cross-tenant, cross-entity, unauthorized actor, revoked membership, and ambiguous mapping cases are denied.
- GLPI ticket entity mismatch, missing/duplicate/inactive/expired xref, replayed nonce, Core Run mismatch, and upstream timeout all fail closed.
- Tests assert that unauthorized cases make no GLPI/Core/Copilot calls beyond the minimum identity/ACL lookup needed to decide.
- Positive authenticated E2E runs against isolated GLPI 11.0.9 + MariaDB 11.4 and a real Core PostgreSQL fixture with signed event issuance and independent ACL decisions.
- Existing Portal routes, navigation, UI handoff, and hourly automations remain covered by regression tests.

## Explicit non-goals

- Do not treat `AIOPS_INTERNAL_TOKEN`, `ADMIN_TOKEN`, or the Portal shared read bearer as actor/tenant authority.
- Do not trust browser headers or ticket description/title markers as identity, tenant, Run association, or authorization.
- Do not register either `POST /api/copilot/ticket/{id}` or `POST /api/copilot/glpi-ticket/{ticket_id}` before the above provider and tests exist.
- Do not weaken the existing policy test that keeps GLPI Copilot fastpaths unmounted without server ACL.
- No production deployment, GLPI writes, Core writes, Copilot activation, or HITL execution is authorized by this design document.

## Current qualification

CODE: read-only xref and upstream adapter candidates exist on the PR branch.
IDENTITY/ACL: NOT IMPLEMENTED; no trusted end-user actor/tenant authority was found in the inspected Core authentication path.
CI: #8549 passed for commit 20dec0b.
DEBIAN/PRODUCTION: unchanged.
E2E: BLOCKED pending a real identity/ACL provider and isolated authenticated integration environment.
