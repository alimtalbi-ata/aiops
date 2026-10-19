#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
for f in db/migrations/*.sql; do
  grep -Eiq '(^|[^a-z])drop[[:space:]]+(database|schema)[[:space:]]+[^i]' "$f" && { echo "FAIL|destructive_sql|$f"; exit 1; } || true
done
for t in runs run_events evidence gates twin_nodes twin_edges incidents observations changes impact_assessments run_stage_state execution_receipts analysis_records critique_records policy_decisions action_proposals approval_records effect_receipts verification_records reconciliation_records learning_cases model_evaluation_runs; do grep -Riq "create table.*aiops\.$t\b" db/migrations || { echo "FAIL|missing_table|$t"; exit 1; }; done
echo SQL_AUDIT=PASS
