#!/usr/bin/env bash
# Poll a reviewed deployment branch. No sudo, no broad compose operations.
set -Eeuo pipefail
umask 077
BASE="${AIOPS_AUTODEPLOY_HOME:-/home/aiops/aiops2-auto-deploy}"
BRANCH="${AIOPS_DEPLOY_BRANCH:-deploy/aiops2-stable}"
REMOTE="git@github.com:alimtalbi-ata/aiops.git"
mkdir -p "$BASE"
exec 9>"$BASE/poll.lock"
flock -n 9 || exit 0
cd "$BASE"
if [[ ! -d repo/.git ]]; then
  git clone --filter=blob:none "$REMOTE" repo
fi
cd repo
git fetch --no-tags origin "refs/heads/$BRANCH:refs/remotes/origin/$BRANCH"
target="$(git rev-parse "refs/remotes/origin/$BRANCH^{commit}")"
applied="$(cat "$BASE/applied.sha" 2>/dev/null || true)"
[[ "$target" != "$applied" ]] || exit 0
# Fail closed: no forced checkout on a dirty working tree.
if [[ -n "$(git status --porcelain)" ]]; then
  echo "ERROR: dedicated checkout has local changes; refusing" >&2
  exit 1
fi
git checkout -B aiops2-approved-deployment "$target"
# Approval is the protected branch itself, not a file inside an unreviewed PR.
test -f deploy/deploy-demo-studio-v2.sh
echo "Approved update: $applied -> $target"
bash deploy/deploy-demo-studio-v2.sh
printf '%s\n' "$target" > "$BASE/applied.sha.tmp"
mv "$BASE/applied.sha.tmp" "$BASE/applied.sha"
echo "Deployment successful: $target"
