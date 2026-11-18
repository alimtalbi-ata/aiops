# Recovery dependency quarantine
Source #279 6c4a8bb03534088355864c1ff41b39e173c2be6a. Exact Git blobs, non-executable filenames, not installed. No migration copied or applied.
- app/core/hitl_reject_delivery.py 2abdb11051355fd028ed68b77439f0c049411a3c
- app/core/itsm_xref.py 13e47970d4ad1803d799e88502346ecb69f69074
- app/shared/core_itsm_xref_read.py 9d90baaeaaaabcc78b89cf1e7ece07c37e321b48
- app/worker/hitl_reject_core_wire.py a50687e8f9fbbe601a770c12b21cdfc15b236174
- app/worker/hitl_reject_notification.py 81068f4d55196fdc2c0896967475d84b670856c4
- tests/test_worker_hitl_reject_notification.py 1b18657aaa3af1ce99ef17296a68c6bfc4842bcc
- tests/test_core_hitl_reject_delivery.py 2cc7774e0478ead25d9012def0d013550bbef7a1
- .github/workflows/hitl-core-worker-pg16-combined-disposable.yml 5792554207258a1c0a8536cc24dabc6267a3b43a

#79 32a537a58edbd1a4a6b97311367f1532788838b8: binding tamper and expiry tests adapted to actual Worker, deterministic repeat is NOT single-use. Original SQLite tests remain unavailable for execution under no DB writes. #49 ancestry not independently verified here. No production changes. Recovery dependencies still need import closure, authenticated ownership, compatible migrations, and separate runtime approval. Historical workflow is deliberately not installed in .github/workflows. No PG16 or Temporal execution.
