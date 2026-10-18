# Canonical contracts

## Run
`run_id`, `incident_id`, `mode`, `scenario_id`, `status`, `version`, timestamps, confidence. `version` is optimistic concurrency control.

## Gate
One gate per `(run_id, stage)`, with state PASS/FAIL/BLOCKED/UNKNOWN, required evidence, actual evidence, decision and reason.

## Evidence
Immutable `evidence_id`, source, observed_at, known_at, claim, confidence, provenance and SHA-256 payload hash.

## TwinNode / TwinEdge
Nodes model business/service/application/infrastructure entities. Edges model dependencies and redundancy. Unknown state is explicit.

## Event
Append-only event sequence per Run. Every stateful execution step must leave an event and, where applicable, evidence references.
