#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
SQL=db/migrations/009_ai_decision_ledger.sql
test -s "$SQL"
for table in analysis_records critique_records policy_decisions action_proposals approval_records effect_receipts verification_records reconciliation_records learning_cases model_evaluation_runs; do
  grep -Fq "create table if not exists aiops.$table" "$SQL" || { echo "FAIL|missing_ledger_table|$table"; exit 1; }
done
grep -Fq "not gold_eligible or (human_reviewed and outcome_verified and not synthetic" "$SQL"
grep -Fq "reject_immutable_mutation" "$SQL"
grep -Fq "guard_action_proposal_insert" "$SQL"
grep -Fq "guard_effect_receipt" "$SQL"
grep -Fq "guard_verification_record" "$SQL"
grep -Fq "proposal_hash" "$SQL"
grep -Fq "idempotency_key text not null unique" "$SQL"
grep -Fq "migration_checksum_changed" deploy/migrate.sh
grep -Fq "BEGIN;" deploy/migrate.sh
grep -Fq "COMMIT;" deploy/migrate.sh
# The runner must keep a single transaction around DDL and its journal entry,
# even when historical SQL migrations include standalone transaction wrappers.
grep -Fq "sed -E " deploy/migrate.sh
grep -Fq "BEGIN|COMMIT" deploy/migrate.sh
migration_fixture="$(mktemp)"
trap 'rm -f "$migration_fixture"' EXIT
printf '%s\n' 'BEGIN;' 'CREATE TABLE example(id integer);' 'COMMIT;' > "$migration_fixture"
normalized="$(sed -E '/^[[:space:]]*(BEGIN|COMMIT)[[:space:]]*;[[:space:]]*$/Id' "$migration_fixture")"
[[ "$normalized" == 'CREATE TABLE example(id integer);' ]] || { echo 'FAIL|legacy_transaction_wrappers_not_removed'; exit 1; }
grep -Fq 'ux_evidence_source_payload_hash' db/migrations/010_evidence_identity.sql
grep -Fq 'ux_evidence_source_external_identity' db/migrations/010_evidence_identity.sql
grep -Fq 'on aiops.evidence(source,external_id)' db/migrations/010_evidence_identity.sql
echo 'MIGRATION_CONTRACT=PASS'
