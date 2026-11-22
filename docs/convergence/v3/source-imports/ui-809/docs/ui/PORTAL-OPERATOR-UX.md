# AIOps 2.0 — Portal operator usability increment

**Branch:** `feat/ui-dark-saas-premium-20261117`  
**Scope:** first-party Portal homepage, progressive enhancement only.

## What changed

- Added an accessible skip-to-content link and labelled the primary navigation.
- Added a compact sticky workspace navigation for Runs, NOC, Digital Twin, integrations, GLPI/ITSM, ACME impact and Explore/Story.
- Added a quick-start block with direct, clearly labelled entry points to the most-used operator workflows.
- Added client-side filtering to the existing Runs table. It filters only rows already rendered in the page; it does not fetch, infer, cache or expose additional Run data.
- Added polite live-region semantics to existing operation result/status areas.
- Kept all existing Portal routes, read-only token exchange behavior, and server-side authorization gates unchanged.
- Added dedicated JavaScript DOM-contract and FastAPI endpoint tests and wired them into GitHub Actions.

## User-facing behavior and safety

The new layer is same-origin, local JavaScript and CSS. It performs no API requests, uses no browser storage, and introduces no new credentials. Existing controls keep their existing behavior. UNKNOWN, UNAUTHORIZED, SYNTHETIC and NOT_TESTED states remain visible and are never promoted to healthy/connected states.

The quick links to ACME Impact and Explore/Story explicitly point to simulation surfaces. External product links remain subject to the existing operator-configured and server-side authorization boundaries.

## Acceptance

- Homepage references `/assets/portal-usability.js`; endpoint serves a local no-store asset.
- Workspace navigation and quick-start links are created once and are keyboard accessible.
- Run filtering operates only on current DOM rows and is idempotent.
- Existing routes and security headers remain present.
- CI runs `test_portal_usability.py`, `test_portal_usability_client.cjs`, and `node --check` for the new script.

## Remaining usability work

This is a first interaction pass, not a full browser UX sign-off. Next improvements should be driven by a real operator walkthrough and screenshots: role-specific navigation after actor/tenant ACL is qualified, server-authorized live Run/Incident lists, better evidence timelines, and operator-tested mobile layouts. Do not enable hidden or simulated operations as shortcuts.
