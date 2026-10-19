#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
SQL=db/migrations/009_ai_decision_ledger.sql
test -s "$SQL"
for table in analysis_records critique_records policy_decisions action_proposals approval_records effect_receipts verification_records reconciliation_records learning_cases model_evaluation_runs; do
  grep -Fq "create table if not exists aiops.$table" "$SQL" || { echo "FAIL|missing_ledger_table|$table"; exit 1; }
done
grep -Fq "gold_eligible or (human_reviewed and outcome_verified and not synthetic)" "$SQL"
grep -Fq "reject_immutable_mutation" "$SQL"
grep -Fq "guard_action_proposal_insert" "$SQL"
grep -Fq "guard_effect_receipt" "$SQL"
grep -Fq "guard_verification_record" "$SQL"
grep -Fq "proposal_hash" "$SQL"
grep -Fq "idempotency_key text not null unique" "$SQL"
grep -Fq "migration_checksum_changed" deploy/migrate.sh
grep -Fq "BEGIN;" deploy/migrate.sh
grep -Fq "COMMIT;" deploy/migrate.sh
echo 'MIGRATION_CONTRACT=PASS'
