# Operational flows

### Live
Ingress → Incident → Run(CREATED) → Temporal → Evidence/Twin/Policy → HITL when required → Verify → Reconcile → Learn.

### Demo
Golden scenario → synthetic Incident → Run(DEMO) → Temporal → synthetic Twin observations → Policy(SIMULATE) → Verify/Reconcile → resolved synthetic Run.

### Replay
Recorded scenario and seed are attached to the Run. No production mutation is allowed.

### Copilot
Portal → Copilot → Core/Twin/Evidence APIs. The Copilot may only state claims supported by these authorities and must say UNKNOWN otherwise.
