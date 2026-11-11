# AIOPS2 handover — 2026-11-11 20:08 Europe/Paris

## Priority
Functional differential audit, not reconstruction. New negative acceptance J-020: malformed yet valid JSON Run field `{"toString":null}` may interrupt incremental row rendering and leave partial rows with global UNKNOWN. See `docs/audits/AIOPS2-RUNS-JSON-COERCION-J020-20261111.md`. Source blob `ac58f73c725f5e088081bffed4478ea18585ef5c`; test specified, not executed.

## Next actions
Execute J-020 in an isolated DOM test against source and candidate; then propose minimal atomic render patch on separate Draft. Check CI against exact head SHA and compare v28/V145 and active Debian only with properly attributed evidence. Keep Dashboard/Core/Twin/Runs, NOC, GLPI, Copilot, Evidence, navigation and consent parity in scope. Do not conflate GitHub source, GitHub CI and Debian host. E2E NOT VERIFIED.

## Guardrails
No merge, deployment, Docker or Debian mutations, cron, secrets, PG/GLPI writes, other stacks, or ACL/HITL bypass. Incident #557 is the operator-confirmed rootful/rootless false diagnostic (aiops UID 1001; socket /run/user/1001/docker.sock; 87 containers/210 images at time of evidence). Host freshness not rechecked. Rollback: close Draft or revert only branch-local documentation commits. Coordinate this file with other Draft handovers; do not overwrite their content.
