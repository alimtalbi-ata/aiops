#!/usr/bin/env bash
# Poll a reviewed deployment branch. No sudo, no broad compose operations.
set -Eeuo pipefail
umask 077
BASE="${AIOPS_AUTODEPLOY_HOME:-/home/aiops/aiops2-auto-deploy}"
BRANCH="${AIOPS_DEPLOY_BRANCH:-deploy/aiops2-stable}"
REMOTE="${AIOPS_DEPLOY_REMOTE:-git@github.com:alimtalbi-ata/aiops.git}"
mkdir -p "$BASE"
exec 9>"$BASE/poll.lock"
flock -n 9 || exit 0

if [[ -e "$BASE/DEPLOYMENT_BLOCKED" ]]; then
  echo "CRITICAL: deployment blocked; manual intervention required" >&2
  exit 1
fi

cd "$BASE"
if [[ ! -d repo/.git ]]; then
  git clone --filter=blob:none "$REMOTE" repo
fi
cd repo
git fetch --no-tags origin "refs/heads/$BRANCH:refs/remotes/origin/$BRANCH"
target="$(git rev-parse "refs/remotes/origin/$BRANCH^{commit}")"
applied="$(cat "$BASE/applied.sha" 2>/dev/null || true)"
[[ "$target" != "$applied" ]] || exit 0

# Quarantine a revision that previously failed deployment.
if [[ -f "$BASE/failed.sha" ]] &&
   [[ "$(cat "$BASE/failed.sha")" == "$target" ]]; then
  echo "BLOCKED: revision previously failed: $target" >&2
  exit 1
fi

# Only accept descendants of the last successfully applied revision.
if [[ -n "$applied" ]]; then
  if ! git cat-file -e "$applied^{commit}" 2>/dev/null; then
    echo "BLOCKED: applied commit unavailable locally: $applied" >&2
    exit 1
  fi
  if ! git merge-base --is-ancestor "$applied" "$target"; then
    echo "BLOCKED: non-fast-forward stable history" >&2
    exit 1
  fi
fi
# Fail closed: no forced checkout on a dirty working tree.
if [[ -n "$(git status --porcelain)" ]]; then
  echo "ERROR: dedicated checkout has local changes; refusing" >&2
  exit 1
fi
git checkout -B aiops2-approved-deployment "$target"
# Approval is the protected branch itself, not a file inside an unreviewed PR.
test -f deploy/deploy-demo-studio-v2.sh
echo "Approved update: $applied -> $target"
if ! bash deploy/deploy-demo-studio-v2.sh; then
  printf '%s\n' "$target" > "$BASE/failed.sha"
  echo "FAILED: revision quarantined: $target" >&2
  exit 1
fi
printf '%s\n' "$target" > "$BASE/applied.sha.tmp"
mv "$BASE/applied.sha.tmp" "$BASE/applied.sha"
echo "Deployment successful: $target"
