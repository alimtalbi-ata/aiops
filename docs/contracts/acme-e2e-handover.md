# ACME E2E handover — 2026-11-18

Source #805 23ed9b4f3f86f05f99630ca3eb37931488d775b0; host #810 aec5a442a9c0718b6603eda9af9a2628c146b2e3. Selective import/adapt: receipt model, gate, historical fixtures, schema and offline workflow. No second orchestrator. V1 retains reason and is structural only, never runtime attestation.

V2 proposed: trusted expected executed SHA, per-stage issuer/digest/UTC, attempt binding, incident/run binding after creation, independent provenance and ticket/Worker digest joins. Missing capability, absent authority or mismatched evidence must block. Core owns finalization; existing IncidentWorkflow remains reference; Twin owner must agree on tenant and approval binding. No runtime claim. CI and exact commit tests pending.

Dependency matrix: receipt/gate ADAPT now; five sandbox capabilities ADAPT pending interface qualification; runner and Demo Studio DEFER until same RunJourney binding; isolated runtime NOT_TESTED. No live effects.
