# INT10-B — SQL dependency mapping (PROPOSED, not applied)
Baseline 7fa2781c2705b5a7920695aa67d34f657f78ab03; handoff #804 6985831779; architect 6985627520.
Source Golden f594d04e02abde19b2299fbb523bf9d0d0e360b8. Static source review only; installed DB state UNKNOWN.
## Current migrations KEEP unchanged
| Current | Role | Mapping |
|---|---|---|
|000|n8n DB|unrelated, never replay|
|001|runs/events/evidence/gates/twin nodes edges|retain; runs status lacks PREPARED|
|002|prevent_append_only and event/evidence triggers|reuse for new immutable receipts; no weakening|
|003|legacy demo graph|not ACME-TEST authority|
|004|incidents/facts/observations/impact/stages|retain; incident state lacks PREPARED|
|005|ACME demo seed|not isolated graph provenance|
|006|execution_receipts|not Worker no-effect receipt|
|007|checkpoints/artifacts/indexes|not durable Temporal prefix proof|
|008|event_key + partial unique (run_id,event_key)|KEEP, Golden015 redundant|
|009|portal actor grants/run tenant bindings|KEEP, no inferred ownership attestation|
|010|OIDC JTI and consumption|KEEP, not Twin nonce or delegation ledger|
|011|GLPI nonce replay|KEEP, not HITL outbox|
|012|GLPI actor user bindings|KEEP, not ITSM xref or immutable function|
|013|execution start intents + immutable trigger|KEEP, not delegation ledger or actual execution proof|

## Historical imports and ordering
All proposals outside db/migrations. Numbering below is dependency order, not allocated migration numbers.
1. Golden009 AI decision ledger blob bfed91982654b6baf0026408fa5134a22af421bb: missing analysis_records, critique_records, policy_decisions, action_proposals, approval_records. Review original constraints/triggers, do not simplify or enable effect/learning paths. Full ledger reference retained. Golden010 evidence identity 1ddafd94639af60ce38b6df0acafd7f63d6b4af2 pending field/index compatibility. Golden012 xref 9408dcf9d92d5bfbdb75968a5a0b0a55f2985457 and 013 delegation 375a9f07edad24877f27276ba2fa87614026f491 are distinct from current 012/013; audit ownership and actor requirements before selecting. No implicit grants or backfill.
2. Golden011 outbox b096af57cb19b9618e3d7d4d68a8ef3d56890934: requires proposals, approvals, runs; REJECT delivery also requires tenant_resource_ownership. Restore historical producer/ownership guards before claiming; no fake ownership from portal binding.
3. Golden014 terminal reject bfaf0161ae3b4c315e09d9cd74d0b6b003d3e315: requires outbox/proposals/runs; replace missing prevent_itsm_xref_mutation with existing prevent_append_only for new table only. Keep receipt/token hash and immutable audit.
4. Golden015 8090ae787400e6a6f87f763b6af9ad2f4287f422: KEEP current008, no duplicate DDL.
5. Golden016 848c6a3a163f227adac17a153e3388e622b989ba +017 fff241c6a1eefcf6a348c9f668c202a63b106176: combine new attempt table with PREPARED allowed; preserve all FKs and immutable trigger using 002. Existing runs/incidents checks require reviewed widening preserving old states; no data rewrite. Scope PREPARED to synthetic sandbox by transaction and further reviewed constraints, not global permission.
6. Golden018 3c05ac7f2ad6ea93f55884300fb52a261cb2dc38: attempt FK, unique nonce digest, terminal receipt immutable via002. Review composite binding of attempt/incident/run/ticket/proposal, atomic resolve and rollback, no mutation of ledger.
7. Golden019 16207a9cde99e312d888e9e0e37efb446a48c4d8: synthetic seed DML only, separate from schema; no execution. Historical site comparison misses NULL (SQL three-valued logic); adapt to IS DISTINCT FROM before any future qualification. Preserve existing topology/IDs, do not conflate with current graph.
8. Policy independent persistence and V4 snapshot/time/impact provenance still PROPOSED; historical policy_decisions table existence alone insufficient, no new shared wire fields without coordination.

## Blockers and test plan
Missing tables above confirmed from migration source, not DB introspection. Need review full Golden009/010/012 constraints and historical Core insert columns, ownership producer, actor ACL and schema readiness before executable DDL proposals. PG16 historical test reference c00ff1e7688022093672132d0ae0ea9e911c8602 retained; prepare real tests for fresh chain, replay/changed request, lock TTL, rollback, immutable receipt, cross tenant, double claim/rotated token, lost ACK, negative DEAD distinct from positive RESOLVED. PG16 NOT_TESTED; no DB or runtime authorization. C tokenless recovery mismatch: retain exact token-fenced terminal_reject; separate adapter only after arbitration, no inferred incident/attempt, no new API.
