# AIOPS2 handover — 2026-11-11 23:10 Europe/Paris

## Scope
Functional differential audit only; no deployment, merge, runtime access or Docker intervention. Source is not evidence of active Debian behavior. E2E remains NOT VERIFIED.

## S-022 isolated candidate
Source blob ac58f73c725f5e088081bffed4478ea18585ef5c: validEnvelope checks dashboard/runs/twin states, but load() used Object.values(data.states) for global read status. Unknown keys (evidence/copilot) could promote global UNKNOWN to READABLE_UNVERIFIED. Fix limits global summary to the three validated keys. This does not change ACL/HITL or the API contract.

## Before / after
| Feature | Before (main source) | Candidate branch | Runtime v28/V145 |
| --- | --- | --- | --- |
| Dashboard/Core/Twin/Runs global state | unknown state keys influence summary | only dashboard/runs/twin influence summary | UNKNOWN |
| Runs visibility | 15 rendered / 100 accepted | unchanged | UNKNOWN |
| NOC/Evidence | independent LIVE attestation required | unchanged | UNKNOWN |
| GLPI/Copilot | tenant ACL/HITL independent | unchanged | UNKNOWN |
| Navigation | not examined this cycle | unchanged | UNKNOWN |

## Negative test
`node --test tests/portal/test_bootstrap_states_whitelist.cjs`: all three recognized panels UNKNOWN, forged extra evidence/copilot READABLE_UNVERIFIED; global output MUST stay UNKNOWN. Test committed but not executed/CI unverified at handover.

## Provenance and rollback
GitHub source blob is source evidence only. CI requires run linked to final head SHA; host freshness unknown. Rootless Docker operator proof (aiops UID 1001, 87 containers, 210 images) establishes #557 as rootful/rootless diagnostic error, not lost storage. No host actions. Rollback: close Draft PR or revert isolated source/test/document commits on branch; no main changes.
