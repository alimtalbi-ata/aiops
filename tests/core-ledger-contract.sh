#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
CORE=app/core/main.py
for route in "analysis-record" "critique-record" "policy-record" "ai-ledger" "proposals" "learning-cases" "proposal_id}/approval"; do
  grep -Fq "$route" "$CORE" || { echo "FAIL|missing_core_ledger_route|$route"; exit 1; }
done
grep -Fq "analysis_and_critic_records_required" "$CORE"
grep -Fq "PASS_policy_requires_clean_validated_analysis_and_critic" "$CORE"
grep -Fq "proposal_hash_mismatch" "$CORE"
grep -Fq "approval_scope_must_match_exact_proposal" "$CORE"
grep -Fq "critical_action_requires_two_distinct_actors_and_roles" "$CORE"
grep -Fq "synthetic_mode_cannot_authorize_real_approval" "$CORE"
grep -Fq "gold_set_requires_live_non_synthetic_human_review_and_verified_outcome" "$CORE"
grep -Fq "execution_allowed':False" "$CORE"
echo 'CORE_LEDGER_CONTRACT=PASS'
