# GLPI ↔ Copilot preservation contract (candidate; not deployed)

## Verified repository gap

The historical source at `5b3b9f327f517e8f5999766389abf69c8a035cf8`
contains `app/portal/glpi_run_context.py` with:
- `POST /api/copilot/glpi-ticket/{ticket_id}` (read GLPI, infer Run from text, query Copilot)
- `POST /api/hitl/glpi-ticket/{ticket_id}/proposal` (guarded synthetic PROPOSED only)
- `POST /api/internal/glpi/runs/{run_id}/sync` (create/update GLPI and GET readback)

The **current main branch** has `/itsm` and `/api/portal/itsm` as
fail-closed handoff only. It does not mount these historical fast paths.
The historical report also mentions `POST /api/copilot/ticket/1`; that
is not the route in the fetched historical source. Route alias/version
must be reconciled from evidence, not invented.

## Preservation / integration gate

1. Preserve the historical GLPI ticket → Copilot answer and source citations,
   including `glpi:/Ticket/{id}`, Core Run, Evidence and AI Ledger.
2. Never treat an explicit Run ID in GLPI ticket text as canonical xref
   evidence. A tenant-scoped server-authorized Core association plus
   authenticated GLPI ticket/entity readback is mandatory **before**
   labeling the Run LINKED or sending its context to Copilot.
3. No user-provided role, tenant, GLPI ID, or boolean readback flags may
   be trusted as ACL/provenance. The candidate authority helper is not
   wired into the runtime and cannot attest provenance itself.
4. HITL proposal must remain PROPOSED, approval_required=true,
   execution_allowed=false; never approve or execute.
5. GLPI sync may update an existing authorized ticket only with a
   verified canonical xref and safe retry/idempotency contract. Do not
   create by searching for `RUN-` in a title. No writes for FS1250 #201.
6. Test real GLPI HTTP in disposable CI only; demonstrate GLPI GET,
   Core Run readback, Copilot HTTP response, evidence sources, tenant
   rejection, ambiguous mapping rejection, and HITL proposal refusal.
7. Record exact SHA and CODE / CI / DEBIAN / E2E evidence separately.
   CI unit PASS is not production readiness.

## Current qualification

- Workflow `AIOps quality gates` on `f72b46b`: SUCCESS, including
  offline identity authority negative tests.
- Newer preservation tests require their own CI run and logs.
- No positive end-to-end current-stack GLPI/Copilot/HITL proof.
- No merge/deploy, production GLPI write, Core DB modification, or
  tenant ACL bypass is authorized.
