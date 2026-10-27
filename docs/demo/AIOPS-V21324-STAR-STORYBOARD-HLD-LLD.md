# AIOps V2.13.24 — ACME STAR storyboard HLD/LLD

Status: **SYNTHETIC_TARGET only; offline candidate, no deployment**. This is a design/acceptance contract, not evidence that runtime screens or DGX analysis were verified.

## HLD

Versioned ACME fixtures (`demo/integrations/v21315/acme-fixtures.json`) → strict CI/incident/identity validation → acyclic dependency graph → 12 STAR narrative scenes → canonical JSON replay SHA-256 → eventual **single** user portal at `10.79.94.202:17777`.

Scenes: intake, detect, correlate, enrich, analyst, critic, policy, ticket/HITL, simulate, verify, close, replay. One business idea per scene. Evidence cues: Grafana detect/verify, n8n correlate/enrich/analyze/simulate, GLPI V1 :8080 ticket/HITL/close. Missing captures stay `MISSING_NOT_CAPTURED`.

## LLD safety contract

Three explicit identifiers `run_id`, `incident_id`, `correlation_id` must be present and distinct; **never synthesize** an ID after RAG. The incident must exist in the versioned ACME fixture, provenance must equal `SIMULATED_TARGET`, all CI dependencies must exist, with no cycles or duplicate identities. Allow only `analyze` and `notify_dry_run`; require `live_remediation: false` for all fixture incidents. The three variants are `single_fabric_loss` P1, `dual_fabric_loss` P1 and `payments_latency` P2. Fabric B is `UNKNOWN_NOT_MEASURED` unless the dual-loss **synthetic** variant is selected.

Topology is not causal proof. SHA-256 replay digest proves determinism of the scenario description, **not** authenticity of screenshots or business outcome. No ticket creation, approval, remediation, DGX attestation, n8n runtime success, or production change is authorized.

## Operator handoff

Keep PR #36 draft, no auto-merge. First qualify code and tests in an isolated checkout. Then reconcile the 02 Webhook→RAG→Canonical Identity→Call Analyst and 03 Prepare Analyst Payload handoff with sanitized V1 traces; reject `RUN_ID_MISSING`. Qualify Chromium interactions against the **exact** portal asset before deployment. Capture only authorized read-only runtime pages at the event moment, with redacted URL, event ID, UTC timestamp, SHA-256, anonymization, expected/observed state. A captured PNG is not by itself an authenticated runtime or business proof. Never restart the incomplete V1 containerd bridge, mutate production services, or expose a second portal.

## Qualification limitations

This document does not claim execution of Chromium on deployed applications, E2E Debian, or a validated V1 02/03 repair. The offline Python implementation and tests are separate candidate artifacts until their exact source is committed and qualified in GitHub CI.
