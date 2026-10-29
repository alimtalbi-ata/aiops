#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
BASE="${AIOPS_AUTODEPLOY_HOME:-/home/aiops/aiops2-auto-deploy}"
BRANCH="${AIOPS_DEPLOY_BRANCH:-deploy/aiops2-stable}"
REMOTE="git@github.com:alimtalbi-ata/aiops.git"

# The installer may never switch the poller to a feature or unreviewed branch.
if [[ "$BRANCH" != 'deploy/aiops2-stable' ]]; then
  echo 'BLOCKED: installer only accepts deploy/aiops2-stable' >&2
  exit 1
fi
mkdir -p "$BASE"
if [[ ! -d "$BASE/repo/.git" ]]; then
  git clone --filter=blob:none "$REMOTE" "$BASE/repo"
fi
git -C "$BASE/repo" fetch --no-tags origin "refs/heads/$BRANCH:refs/remotes/origin/$BRANCH"
target="$(git -C "$BASE/repo" rev-parse "refs/remotes/origin/$BRANCH^{commit}")"

# Never infer deployed code from a Docker image tag or the approved Git ref.
# applied.sha must have been provisioned separately after an operator checked
# the deployed revision. This comparison is NOT independent host attestation.
if [[ ! -f "$BASE/applied.sha" || -L "$BASE/applied.sha" ]]; then
  echo 'BLOCKED: operator-provisioned regular applied.sha required; no automatic bootstrap' >&2
  exit 1
fi
if [[ "$(stat -c %s -- "$BASE/applied.sha")" != 41 ]]; then
  echo 'BLOCKED: applied.sha must contain exactly one 40-character SHA and newline' >&2
  exit 1
fi
applied="$(cat -- "$BASE/applied.sha")"
if [[ ! "$applied" =~ ^[0-9a-f]{40}$ ]] ||
   ! git -C "$BASE/repo" cat-file -e "$applied^{commit}" 2>/dev/null; then
  echo 'BLOCKED: invalid or unavailable applied commit' >&2
  exit 1
fi
if [[ "$applied" != "$target" ]]; then
  echo 'BLOCKED: approved target differs from operator-provisioned applied.sha; manual release review required' >&2
  exit 1
fi

# Install only after validation; cron installation must not trigger a rollout.
install -m 700 "$(dirname "$0")/poll-approved-deploy.sh" "$BASE/poll.sh"
line="*/5 * * * * /bin/bash $BASE/poll.sh >> $BASE/poll.log 2>&1"
{ crontab -l 2>/dev/null | grep -Fv "$BASE/poll.sh" || true; printf '%s\n' "$line"; } | crontab -
echo "Cron installed (every 5 minutes); applied SHA from operator-provisioned file: $applied (NOT_ATTESTED)"
