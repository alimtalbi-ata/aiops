#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
BASE="${AIOPS_AUTODEPLOY_HOME:-/home/aiops/aiops2-auto-deploy}"
BRANCH="${AIOPS_DEPLOY_BRANCH:-deploy/aiops2-stable}"
REMOTE="git@github.com:alimtalbi-ata/aiops.git"
mkdir -p "$BASE"
# The script itself is installed outside the checkout; cron does not execute code from an unapproved feature branch.
install -m 700 "$(dirname "$0")/poll-approved-deploy.sh" "$BASE/poll.sh"
if [[ ! -d "$BASE/repo/.git" ]]; then
  git clone --filter=blob:none "$REMOTE" "$BASE/repo"
fi
git -C "$BASE/repo" fetch --no-tags origin "refs/heads/$BRANCH:refs/remotes/origin/$BRANCH"
target="$(git -C "$BASE/repo" rev-parse "refs/remotes/origin/$BRANCH^{commit}")"
# Bootstrap without redeploying the already-running V2 portal.
if [[ ! -e "$BASE/applied.sha" ]]; then
  docker inspect aiops2-rebuild-portal --format '{{.Config.Image}}' | grep -Fx 'aiops2-portal:demo-studio-v2-20261028' >/dev/null || {
    echo "Current portal is not the confirmed V2 image; refusing bootstrap" >&2; exit 1;
  }
  printf '%s\n' "$target" > "$BASE/applied.sha"
fi
line="*/5 * * * * /bin/bash $BASE/poll.sh >> $BASE/poll.log 2>&1"
{ crontab -l 2>/dev/null | grep -Fv "$BASE/poll.sh" || true; printf '%s\n' "$line"; } | crontab -
echo "Cron installed (every 5 minutes); current approved revision: $(cat "$BASE/applied.sha")"
