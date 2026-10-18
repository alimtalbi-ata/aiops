# Operations

1. Run static qualification.
2. Validate disk space and Docker availability on the target VM.
3. Load only validated Docker images/binaries.
4. Deploy the clean-slate stack without stopping the legacy stack.
5. Apply idempotent schema migrations.
6. Run service health and network reachability tests.
7. Run synthetic scenarios and verify canonical IDs end-to-end.
8. Verify outbox/receipt idempotence and restart/replay behavior.
9. Create QUALIFIED marker only after all runtime gates pass.
10. Retire legacy explicitly and separately.
