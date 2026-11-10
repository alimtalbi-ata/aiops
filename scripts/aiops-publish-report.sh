#!/usr/bin/env bash
# SRV-DEB-05 report-only publisher; installed at ~/.local/bin/aiops-publish-report
set -Eeuo pipefail
umask 077
REPO="git@github.com:alimtalbi-ata/aiops.git"
BRANCH="ops/debian-runtime-reports"
STATE="${HOME}/.local/state/aiops-debian-agent"
CHECKOUT="${STATE}/report-git"
SOURCE="${STATE}/latest.json"
TARGET="ops/debian-reports/SRV-DEB-05/latest.json"
mkdir -p "$STATE"
exec 9>"$STATE/publish.lock"
flock -n 9 || exit 0
test -s "$SOURCE" || { echo "REPORT_PUBLISH=FAILED reason=missing_local_report"; exit 1; }
export GIT_SSH_COMMAND="ssh -o BatchMode=yes -o ConnectTimeout=10"
if [[ ! -d "$CHECKOUT/.git" ]]; then
  git clone --quiet --single-branch --branch "$BRANCH" "$REPO" "$CHECKOUT"
fi
cd "$CHECKOUT"
if [[ -n "$(git status --porcelain)" ]]; then
  echo "REPORT_PUBLISH=FAILED reason=dirty_checkout"
  exit 1
fi
git fetch --quiet origin "$BRANCH"
git checkout --quiet "$BRANCH"
git merge --ff-only --quiet "origin/$BRANCH"
mkdir -p "$(dirname "$TARGET")"
cp "$SOURCE" "$TARGET"
git add -- "$TARGET"
if git diff --cached --quiet; then
  echo "REPORT_PUBLISH=UNCHANGED"
  exit 0
fi
git -c user.name="AIOps2 Debian Reporter" \
    -c user.email="aiops2-reporter@users.noreply.github.com" \
    commit --quiet -m "ops(debian): update SRV-DEB-05 report"
if git push --quiet origin "HEAD:refs/heads/$BRANCH"; then
  echo "REPORT_PUBLISH=PUBLISHED"
else
  echo "REPORT_PUBLISH=FAILED reason=push_rejected"
  exit 1
fi
