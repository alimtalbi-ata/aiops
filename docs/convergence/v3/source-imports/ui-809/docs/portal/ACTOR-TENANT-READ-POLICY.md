# Proposed actor/tenant read policy

The isolated policy in app/portal/actor_read_policy.py does not authenticate users and is not wired into any route. Its role matrix is a proposal subject to business approval.

N1: incident/run read. N2: additionally evidence read. N3: additionally decision read. Manager: incident/run/decision read, no raw evidence by default. All cross-tenant access, unknown claims and writes are denied.

Before enabling routes: select and configure a trusted identity provider; verify issuer, audience, signature and expiry; resolve server-managed actor and tenant membership; establish tenant ownership of resources from trusted storage; enforce permission on each query and detail endpoint; test cross-tenant enumeration and revocation; implement secure sessions and CSRF controls before cookie-based actions. Do not populate Principal from browser headers or shared bearer tokens.

Existing NOC tenant fences and all LIVE restrictions remain unchanged. No new authorization grant is active. CI unit tests cover the isolated rule only; end-to-end identity and storage authorization remain unqualified.
