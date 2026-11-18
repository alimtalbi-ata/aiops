# INT10-B B3 — ownership and terminal candidate
Parent a77ab28af10bc8b3b9ef454b42ccc790431eb611; Golden f594d04e02abde19b2299fbb523bf9d0d0e360b8; #234 historical e6dc55536a1e2daabc59420a94c48eae8e9c042a.
CONFIRMED: app/core/itsm_xref.py blob 13e47970d4ad1803d799e88502346ecb69f69074 verifies deployment-owned HMAC proof file aiops.core-ownership-proof.v1; separate key, canonical row payload. tests/test_core_itsm_xref_postgres_integration.py blob f5e524db2a9dbff77233a25ed6868058ec7fe01d inserts fixture rows and signs them. This is not authenticated ingestion. Operational producer UNKNOWN; never infer from portal bindings. Immutable ownership PK prevents refreshing same resource under existing schema while B requires <=300s freshness; lifecycle needs explicit design/arbitration, not mutation or fake proof.
Existing B app/core/hitl_reject_delivery_int09.py: claim row lock SKIP LOCKED, 30s token rotation, max 8, ACK token bound, terminal distinct permission, same transaction DEAD+receipt. Exact eight keys preserved. C tokenless adapter BLOCKED per #804 6986113544. Positive RESOLVED separate.
Candidate outbox-terminal.sql.proposed derived from Golden011/014, adds composite proposal and approval identity, REJECT-only state checks, deferred DEAD/receipt pairing, current002 append-only trigger. No runtime grants or routes. Fresh-only, not replay-idempotent. Does not enforce every legal transition, token digest or payload hash at DB layer; these require further design and tests; no authorization inferred. PG16 NOT_TESTED (including char/text FK compatibility). Proposal changes deliberately restrict APPROVE delivery and PENDING attempts=0 to observed B path; other producer semantics must be checked. Ownership table not fabricated.
## PG16 test matrix (planned, not run)
- positive fresh chain, exact B claim/ACK/DEAD SQL, commit and immutable receipt readback
- mismatched run/proposal/hash/revision/approval, foreign tenant and missing/stale/forged ownership refused
- concurrent claim SKIP LOCKED, expired lease rotated; old token ACK and DEAD refuse
- attempt 7 terminal refusal, attempt 8 before expiry refusal, terminal permission missing refusal
- DEAD without receipt and receipt without DEAD fail at commit; injected insert failure rolls back DEAD
- lost ACK replay, lost terminal response replay, changed token or hash refusal
- no APPROVE, effect, real GLPI, inferred incident/attempt, or positive RESOLVED
- verify duplicate evidence preflight, no purge, no historical data rewrite
No DB/lab launch/migrations/merge/runtime. RT10 NO-GO.
