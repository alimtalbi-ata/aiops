# Final architecture review V7.4

- Simulation observations are run-scoped; they no longer contaminate the canonical Twin.
- Evidence idempotency is enforced in PostgreSQL, not only in application code.
- Integration traffic is isolated from the control network for n8n.
- State-changing Core commands generate an outbox event in the same transaction as the state change.
- Copilot reports citations and avoids presenting a fabricated confidence score when evidence is absent.
- Legacy retirement remains a separate approved operation.
