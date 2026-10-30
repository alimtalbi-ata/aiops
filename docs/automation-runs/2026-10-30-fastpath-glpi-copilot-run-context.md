# FASTPATH — GLPI ticket to Copilot run-context qualification

Date: 2026-10-30
Repository: alimtalbi-ata/aiops
Branch: feat/portal-hitl-copilot-glpi

## Verified execution

The portal authenticated successfully to GLPI and discovered 14 AIOps2 demo tickets. Ticket `1` was read successfully:

- Title: `[AIOps2][DEMO][SYNTHETIC] P1 Payments - RUN-818D2B05974AE5F8`
- GLPI source: `glpi:/Ticket/1`
- Associated run: `RUN-818D2B05974AE5F8`

The portal Copilot endpoint `POST /api/copilot/ticket/1` returned HTTP 200 when supplied with the run ID. Core endpoint `GET /api/runs/RUN-818D2B05974AE5F8` also returned HTTP 200.

The run reports status `RESOLVED`, mode `DEMO`, scenario `SCN-GOLDEN-PAYMENT-P1`, incident `INC-DEMO-GOLDEN-PAYMENT-871f9f426e954fe2abdff6497443e945`, version 29 and overall confidence 0.94.

Copilot returned sources:
- `core:/api/runs/RUN-818D2B05974AE5F8`
- `core:/api/runs/RUN-818D2B05974AE5F8/evidence`
- `core:/api/runs/RUN-818D2B05974AE5F8/ai-ledger`
- `glpi:/Ticket/1`

The response summarized 13 linked evidence records, one Analyst analysis and one Critic review. It reported the latest Critic review as validated with zero objections.

## Qualification caveats

This is a synthetic DEMO run, not a production incident. The run evidence includes 11 lifecycle markers that are not diagnostic evidence. The reported 0.94 confidence is from the deterministic synthetic baseline and is not a calibrated production model probability.

Copilot explicitly states that no remediation, HITL approval, or GLPI ticket creation was performed. This execution proves GLPI-to-Copilot run-context retrieval only; it does not prove HITL proposal persistence, portal display, or GLPI write-back.

## Next implementation work

1. Trace Analyst/Critic ledger records and evidence references into a persisted, ticket-linked HITL proposal.
2. Expose the proposal in Policy Center and verify it through the read API.
3. Keep remediation in simulation / pending-human-approval; do not execute infrastructure mutations.
4. Add E2E coverage for GLPI authentication, ticket read, run lookup, Copilot source assertions, HITL persistence and portal visibility.
5. Publish machine-readable test output and wire the test into scheduled Quality Checks.

## Acceptance criteria still open

- [ ] HITL proposal persisted and linked to GLPI ticket 1 and run RUN-818D2B05974AE5F8
- [ ] Proposal visible through the portal / Policy Center
- [ ] Evidence provenance distinguishes diagnostic evidence from lifecycle markers
- [ ] E2E regression test passes
- [ ] Scheduled Quality Checks execute the regression test
- [ ] No remediation without explicit human approval
