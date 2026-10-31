#!/usr/bin/env bash
# Install the AIOps2 Debian reporter from the reviewed PR branch.
# Run as the unprivileged aiops account from any working directory.
set -Eeuo pipefail

REPO="alimtalbi-ata/aiops"
REF="test/debian12-install-runtime-qualification-20261031"
SOURCE="https://raw.githubusercontent.com/${REPO}/${REF}/scripts/debian-readonly-reporter.py"
BIN_DIR="${HOME}/.local/bin"
STATE_DIR="${HOME}/.local/state/aiops-debian-agent"
CONFIG_DIR="${HOME}/.config/aiops"
TOKEN="${CONFIG_DIR}/github-token"
DEST="${BIN_DIR}/aiops-debian-reporter"
CRON_MARKER="# AIOPS2_DEBIAN_REPORTER_V1"
CRON_LINE="* * * * * /usr/bin/flock -n ${STATE_DIR}/cron.lock /usr/bin/python3 ${DEST} >> ${STATE_DIR}/cron.log 2>&1 ${CRON_MARKER}"

if [[ "$(id -un)" != "aiops" ]]; then
  echo "BLOCKED: run this installer as Linux account aiops, not root." >&2
  exit 2
fi
if [[ ! -f /etc/os-release ]] || ! grep -q '^ID=debian' /etc/os-release; then
  echo "BLOCKED: this installer is intended for Debian." >&2
  exit 2
fi
for cmd in curl python3 install crontab flock; do
  command -v "$cmd" >/dev/null 2>&1 || { echo "BLOCKED: missing required command: $cmd" >&2; exit 2; }
done
if [[ ! -f "$TOKEN" || -L "$TOKEN" ]]; then
  echo "BLOCKED: provision the fine-grained GitHub token at $TOKEN first." >&2
  exit 2
fi
if [[ "$(stat -c '%a' "$TOKEN")" != "600" ]]; then
  echo "BLOCKED: token file must have mode 600." >&2
  exit 2
fi

install -d -m 700 "$BIN_DIR" "$STATE_DIR" "$CONFIG_DIR"
TMP="$(mktemp "${STATE_DIR}/reporter.XXXXXX")"
trap 'rm -f "$TMP"' EXIT
curl --fail --silent --show-error --location --max-time 20 "$SOURCE" -o "$TMP"
python3 -m py_compile "$TMP"
install -m 700 "$TMP" "$DEST"
python3 "$DEST" --help >/dev/null 2>&1 || true

CURRENT="$(crontab -l 2>/dev/null || true)"
if ! grep -Fq "$CRON_MARKER" <<<"$CURRENT"; then
  { printf '%s\n' "$CURRENT"; printf '%s\n' "$CRON_LINE"; } | crontab -
fi
echo "AIOPS2_DEBIAN_REPORTER_INSTALLED=1"
echo "SCHEDULE=* * * * * (collection every minute; GitHub publication remains throttled to every 15 minutes)"
echo "LOCAL_REPORT=${STATE_DIR}/latest.json"
echo "GITHUB_REPORT_BRANCH=ops/debian-runtime-reports"
