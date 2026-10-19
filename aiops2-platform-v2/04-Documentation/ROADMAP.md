# AIOps 2.0 roadmap

- V2.0: incident API, PostgreSQL, deterministic safety policy, Compose isolation, smoke tests.
- V2.1: Temporal durable workflow; retries, activity timeouts, replay and idempotency qualification.
- V2.2: analyst/critic provider abstraction, local OpenAI-compatible inference, structured output, evidence citations, abstention and RAG.
- V2.3: CMDB CI resolution, GLPI bridge, bidirectional HITL and approval audit.
- V2.4: isolated chaos scenarios, deterministic seeds, replay and SLO/load testing.
- V2.5: allowlisted remediation only, dry-run, preconditions, ownership/fencing, transaction ledger, verification and rollback.

LLM output must never authorize remediation by itself. Every increment requires tests, manifests and clear separation of executed versus planned qualification.