# C9 — disposable qualification protocol (DESIGN ONLY)

Authorization: separate Central GO required before any service, DB write, migration,
route/auth activation or lab launch. Existing C offline workflow must not launch this.
Historical source #279 6c4a8bb03534088355864c1ff41b39e173c2be6a,
local inactive test_worker_core_pg16_temporal_combined.py.reference.
B6 6986691809: proposed DDL only; authenticated ownership producer/key/proof UNKNOWN.
No operational tenant claim or durable B/C qualification until resolved.

## Reuse and adaptation gates
Historical setUpClass creates fixed-name DB, applies historical migrations, patches
environment/auth and mounts router; setUp force-marks pending/leased DEAD; teardown
drops DB WITH FORCE. Do not port or execute these lifecycle operations. Historical
gateway records raw ACK body (token); do not export it. Preserve actual wire validators,
SyntheticRejectSink, fault sequences and assertions only after review. Use B-approved
schema and fixture lifecycle, separate authorization before implementation/launch.
No direct DEAD SQL as evidence of terminal_reject. Historical HMAC fixture is synthetic.

## Scenario matrix (all NOT_TESTED on INT10)
| Historical test | Required future evidence |
|---|---|
| 01 unsigned source | no lease, no signal, no receipt |
| 02 HTTP/Worker restart | committed ACK readback, replay identity, PID evidence |
| 03 claim expiry/fencing | current token rotation, old token refused, exact tenant/owner/revision |
| 04 gateway ACK loss | commit before deterministic TCP close, no duplicate signal after restart |
| 05 independent TCP + server restart | persistent history, changed server PID, same workflow ID |
| 06 two Workers | competing processes, one accepted claim, durable history after server restart |
| 07 multiprocess stale ACK | old fence denied, distinct durable REJECT receipts |
| 08 cross-tenant | foreign claims/ACK denied, two separate tenant receipts; native terminal path separately required |

## Preflight and lifecycle design
- Central-approved exact C/B baseline and dependencies; approved SQL/model and isolated
  synthetic ownership fixtures explicitly labeled non-authoritative.
- Unique job-scoped DB, task queue, workflow ID and temporary directory; no inherited
  production credentials, network routes, volumes or host mounts. Explicit allowed local
  endpoints; external egress denied during test execution. No default DATABASE_URL fallback.
- Record process IDs and creation identities, service versions, image digests, exact SHA,
  test selection and fault timestamps. Never record raw tokens/bearers/connection strings.
- Assert no-effect flags and no approval authority in every scenario. Distinguish callback
  exception, deterministic TCP close, actual packet loss, process kill and server restart.
- Cleanup on success/failure/timeout using job-owned resources only; verify resource absence
  and sanitized evidence before upload. Missing cleanup evidence = NOT_QUALIFIED.
- Negative terminal_reject and positive resolve remain separate; no inferred incident join.
  No Epoch; attempts are retry budget only. No fake ownership refresh.

No executable harness, service definition or trigger added. PG16, Temporal, network,
teardown and image build remain NOT_TESTED. RT10 NO-GO.
