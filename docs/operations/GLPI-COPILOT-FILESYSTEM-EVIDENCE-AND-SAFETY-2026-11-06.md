# GLPI Copilot — filesystem evidence, correlation and safe routing (FS491–FS507)

Status: **observed lab behavior and unmerged candidate work**, 2026-11-06. This is not a deployment or live qualification record. This page is a continuity handoff for the next maintainer; revalidate against the running source before changes.

## Runtime boundaries

- GLPI 11.0.9 hosts tickets and public followups. The GLPI Copilot bridge runs from a separate operations script and is scheduled by a host launcher/cron. **Executing the bridge or cron may post public GLPI followups**; never use it as a read-only test.
- The Copilot API currently uses deterministic factual responses and synthetic lexical runbooks, not a qualified LLM inference service. The bridge's filesystem branch can bypass the Copilot API for filesystem questions.
- The active bridge is `~/aiops2-operations/glpi_copilot_bridge.py`. Candidate files `glpi_copilot_bridge.fs*-candidate.py` are separate, non-deployed experiments. Never infer deployment from candidate creation.
- Snapshot files in the Portal runtime: `/tmp/fs373-evidence.json`, `/tmp/fs374-services.json`, `/tmp/fs375-correlation.json`, `/tmp/fs376-audit.json`. They are **runtime evidence, not repository source**.

## Snapshot schemas and freshness

FS373: `schema, source, collected_at, filesystem, used_percent, total_kib, used_kib, available_kib, file, df_raw, du_raw, ls_raw, remediation_executed`. FS374: `schema, collected_at, sources, remediation_executed`; source keys `core_incidents, core_runs, worker_metrics, prometheus_fs_usage`, each with availability/value information. The bridge checks `collected_at` against UTC, rejecting future timestamps and snapshots older than **600 seconds**. The presence of a field or reachable endpoint does not prove a service outage, a Critic decision, or approval.

FS375 and FS376 are **ticket-scoped** correlation/audit evidence. For the real filesystem alert ticket #147, the inspected snapshots had no confirmed RUN IDs or confirmed links, and no HITL authorization. Candidate incidents or filesystem observations do not create a Core RUN correlation.

## Ticket isolation and Core proof contract

- Ticket **#147** is a real filesystem alert; **do not attach the demo RUN to it**.
- Ticket **#148** is a demo ticket with a separately verified Core RUN; its Critic state was BLOCKED / HUMAN_APPROVAL and Policy/HITL remained PENDING at inspection time. Re-query Core for current status; this is not a permanent assertion.
- FS401 bridge verification: exactly one RUN identifier in the GLPI title; same RUN present in the ticket description; exactly one incident identifier in description; GET Core `/api/runs/<RUN>`; returned RUN and incident must match; exactly one `DGX_CRITIC` / `CRITIC_COMPLETED` event. Only then set `correlation_verified=True`.
- Policy and HITL stage values are reported separately. **PENDING is not approval.** Missing or ambiguous proof must remain unverified. Do not transfer correlation across tickets or infer authorization from followups, historical tickets, filesystem evidence, or endpoint reachability.

## Response behavior and candidates

- Active bridge: filesystem evidence/report path; static filesystem answers can be generic. No candidate below is deployed.
- FS493 candidate: direct blocking response only after strict correlation; otherwise explicitly says no verified RUN/incident/Critic linkage.
- FS501 candidate: removed generic `pourquoi` trigger from blocking routing, preserving filesystem questions.
- FS504 candidate: pure `classify_copilot_intent(question)` with priority **ACTION > BLOCKING > EVIDENCE > IMPACT > FILESYSTEM**; classifier not yet connected.
- FS507 candidate: connects classifier; ACTION returns a diagnostic-only, non-operational refusal to authorize deletion/remediation; BLOCKING uses existing correlation guard; EVIDENCE/IMPACT/FILESYSTEM still use prior report fallback. **FS507 has syntax validation only; functional regressions have not yet been run.** Its ACTION branch returns a safety summary rather than the full collected report; retaining useful evidence without weakening safeguards is open work.
- The classifier is lexical/heuristic; its 13 passing unit examples do not demonstrate broad language robustness or production suitability.

## Tests and evidence of qualification

- FS494B: 5/5 offline mocked cases; FS495: 5/5 additional correlation adversarial cases; FS502: 4/4 routing regression cases for FS501; FS505: 13/13 isolated classifier cases for FS504.
- FS503 mapped snapshot fields; FS506 inspected candidate source and confirmed 600-second freshness checks, Core correlation guard, and safety footer.
- Tests used AST-extracted functions, fake Core responses, and mocked file reads. They did **not** write GLPI, call live Core, approve HITL, execute remediation, or qualify the running bridge. The tests cover different candidate versions and **must not be added together as a single FS507 test suite**.
- Candidate FS507 SHA-256 (lab output): `4f4dab5e86cb15eb97e2a0d69a101a1f95088baac0d478633c5c6c54f3e1e8fe`. Active bridge SHA-256 at that time: `d97379be6aa7df98dfa43036f00ca59ec3486f20d8ace32b7f3376a241b9f9fa`. Hashes are point-in-time fingerprints, not deployment attestations.

## Hard safety constraints

**Never** delete, truncate, or alter the filesystem lab fill file without freshly verified, action-specific human authorization for the real ticket. Never auto-approve HITL, override Critic BLOCKED, run remediation, or close tickets. Avoid live bridge/cron invocation without explicit authorization because GLPI followups are public. Do not expose credentials or unredacted private operational data in GitHub.

## Next steps (not completed)

1. Run **FS508 offline regression** against FS507, including mixed ACTION/HITL prompts, ticket isolation, stale snapshot failures, and missing/duplicate Critic evidence.
2. Design EVIDENCE/IMPACT responses grounded in fresh snapshots, explicitly distinguishing observed saturation from proven business impact.
3. Preserve useful evidence in direct answers while keeping correlation and action authorization fail-closed.
4. Review candidate changes and tests in a PR; only consider deployment after explicit authorization, backups, and a rollback plan.
5. Keep project continuity, architecture, decision log, component catalog and qualification records synchronized as follow-up documentation work. This focused page does not replace those documents.
