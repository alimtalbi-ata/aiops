# ACME E2E handover — 2026-11-18

Source #805 23ed9b4f3f86f05f99630ca3eb37931488d775b0; host #810 aec5a442a9c0718b6603eda9af9a2628c146b2e3. Selective import/adapt: receipt model, gate, historical fixtures, schema and offline workflow. No second orchestrator. V1 retains reason and is structural only, never runtime attestation.

V2 proposed: trusted expected executed SHA, per-stage issuer/digest/UTC, attempt binding, incident/run binding after creation, independent provenance and ticket/Worker digest joins. Missing capability, absent authority or mismatched evidence must block. Core owns finalization; existing IncidentWorkflow remains reference; Twin owner must agree on tenant and approval binding. No runtime claim. CI and exact commit tests pending.

Dependency matrix: receipt/gate ADAPT now; five sandbox capabilities ADAPT pending interface qualification; runner and Demo Studio DEFER until same RunJourney binding; isolated runtime NOT_TESTED. No live effects.

## Worker capability selective import
Golden 2834158bfff6556673a8d993da9ee1b8e6f5f465, worker blob 58b89012606a90ac76ab7194463563efa176b2db, original test blob 292290f46bde0741fabd339a1c1bb96048daa3c0. Import pure no-effect activity only; 28 portable test methods retained, four route/Temporal integration tests deferred until host registration. Injected GET transport is a test seam, not a runtime authority. The module must not be exposed directly to caller-controlled readbacks. Temporal registration, authenticated transport, Core schema and Twin approval remain prerequisites; no second orchestrator. #812 STORY_OFFLINE UNBOUND never promoted to ACME-TEST. #811 should show receipt_phase PRE_RESOLUTION, ticket ID and no-effect flags only, not RESOLVED. Audit authority label in fixture result is not evidence of actual Temporal history.
