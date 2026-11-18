# REUSE & PORT — INT08C
Baseline #818 13aabde7f05632a36679b96e11334add406d62ac. Source #426 add0595dfa6f2719f4666881ab92c042f0336951 blob 7809181bccc29d4ab8d0b0aed9753398234e03b4: four receipt tests copied with current verify_no_effect_receipt and seven-identity fixture checks. No production code changed. Parallel synthetic receipts are NOT a durable idempotency proof.

## Pending arbitration (not applied)
- #466 b483a8c508dd84817d35acf08eddd4744092732c admit_resume: action/workflow/epoch binding only; reject LIVE and do not translate ELIGIBLE/ALLOW/human approval into simulated authority.
- #348 c280e3122a6f8131f87933bd8e99ccd9fb7d24f3: registered activities and recover_terminal_once; port only into existing workflow after approval; preserve verify_no_effect_receipt. Pure decoder surrogate checks, typed impacts, fresh second fence, canonical snapshot and strict effect count proposed; streaming reader requires transport arbitration.
- #79 32a537a58edbd1a4a6b97311367f1532788838b8 propose/approve/dry_run: one-use/TTL/race invariants; no SQLite production store.
- #251 dcee21f059d31ce28cc43ba25a00fd1fd707dc48 deliver_core_reject_once: missing notification adapter and Core claim/ACK; #344 567cdad18571ccea8f0f65e3ddf721d92f38de95 claim_reject/ack_reject/terminal_recover: storage and auth arbitration.
- #802 f594d04e02abde19b2299fbb523bf9d0d0e360b8 Core PREPARED/resolve and Twin/Policy per B 6983411880; do not bypass VERIFY/RESOLVE; independent postcheck/history prefix still required. Historical migration numbers 009–013 conflict with baseline; no apply.
- #279 6c4a8bb03534088355864c1ff41b39e173c2be6a combined PG16 and Temporal dev SQLite restart suite; #325 8106ce7eb51cd60f465af1133a4cb738bb2de330 rollback suite. Recover test harness/config/runbook after dependency reconciliation, no service run or import of old runtime workflow. Existing INT07 collector and B validators remain authoritative contracts.
- Source #348 test_12/28–32/39 require real registration or transport boundary review; #426 other matrices need individual comparison. No lab, no migrations, no API/auth/DB change. Runtime UNKNOWN.
