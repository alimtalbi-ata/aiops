# P0 — ACME enterprise Explore/Story 60 CI — 2026-10-28 11:15–11:18 Europe/Paris

## Starting state
- Main verified immediately before branching: `5d757869a46f427b1885a19ce019ca29a18063fd` (Core NOC auth PR #124).
- PRs inspected: #36, #37, #39, #41, #43, #120, #124 and open PR index; reused existing v1 ACME contract from main, itself a targeted port of #36. No merge of #36 or #120.
- Continuity: `docs/PROJECT-CONTINUITY.md`, `docs/DEMO-REPLAY-STORY.md`, `docs/COMPONENT-CATALOG-AND-REUSE.md`.

## Changes
- `app/portal/acme_fixture_contract.py`: deterministic `expand_enterprise_fixture` preserving exact v1 fields, canonical six CI and SAN → Host → VM → Payments dependency path; 60 CI and six simulated incidents.
- `app/portal/acme_enterprise_read_model.py`: 4 sites, 5 business services, six fixed-clock events and six synthetic tickets with explicit absent Core/GLPI IDs; byte-bound fixture digest and canonical dataset digest.
- `app/portal/main.py`: read-only `/api/demo/acme-enterprise/explore` and `/api/demo/acme-enterprise/story`, both from the same builder.
- `tests/test_acme_enterprise_read_model.py`: negative LIVE/action/cycle/noncanonical/symlink/invalid fixture, v1 non-regression, deterministic IDs and API parity.
- `.github/workflows/quality.yml`: add tests to existing quality workflow, no parallel CI.

## Commits and PR
- `7d9fbcf155a262c7d7203936c4c64f59de09c0b2`: strict v1 extension.
- `d39e6735bc291984e57867c56ce1b00733f037eb`: enterprise read model.
- `c8f837e884916d9ff494d80a9df967f1e8724794`: portal router.
- `cf24e68b8778d5d11e7cb6b18abc22c51f2d816e`: contract/security tests.
- `f88a955ba72894ec5b5234d3231c64af1f0d3d58`: existing quality workflow.
- Draft PR: https://github.com/alimtalbi-ata/aiops/pull/127

## Verification / limits
- GitHub Actions result: PENDING verification on exact final HEAD. No test is claimed PASS in this journal before confirmed completion.
- All synthetic fixtures are `SIMULATED_TARGET`; timestamps are scenario-clock values, not observed events. `glpi_ticket_id` and `core_run_id` remain null. No backend writes or LIVE actions.
- Core/Twin/Temporal/GLPI real-container integration for this new projection: NOT_TESTED. PR #120 qualifies a real GLPI negative HTTP path only, not a positive ticket correlation.
- Risk: 60-CI inventory is a deterministic fictional target, not a discovered CMDB. Site assignment is scenario metadata, not verified topology. Existing v1 fixture remains the six-node seed; future integration must not mistake the expansion for production inventory.
- No Debian access, deployment, production secrets, merge or LIVE execution.

## Next micro-lot
Render Explore site/service filters and Story timeline from these exact read endpoints, with visible synthetic provenance; then test real ephemeral Core/GLPI joins separately without fabricating a ticket.
