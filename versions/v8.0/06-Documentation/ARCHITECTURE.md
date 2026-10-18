# Architecture V8.0

Core owns canonical Run lifecycle. Temporal is the sole workflow executor. PostgreSQL stores durable canonical state. Twin owns topology/context. Evidence owns provenance. RAG supplies retrieved context. Intelligence analyzes. Policy authorizes or blocks. Integration is the only ITSM boundary. Portal consumes projections rather than directly coupling to every database.

Every distributed operation carries correlation_id; incident processing carries incident_id and run_id. Evidence has observed_at and known_at so Replay can answer both when a fact happened and when AIOps knew it. Decisions and remediations reference the same run. Outbox and receipts make external delivery auditable and idempotent.

Networks are intentionally segmented: front, core, data, temporal, observability and itsm. Data/Temporal/Observability/ITSM networks are internal. Only explicitly approved UI ports are published.

DEMO/REPLAY/STORY never mutate production. Unknown evidence fails closed. Legacy retirement requires a runtime qualification marker.
