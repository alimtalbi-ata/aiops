#!/usr/bin/env bash
# Install a separate pinned Codex queue poller; never edits the deployment poller.
set -Eeuo pipefail
umask 077
REPO="alimtalbi-ata/aiops"
BRANCH="design/coordination-bus-20261109"
SHA="${1:?Usage: install_codex_poll_cron.sh <40-char-verified-sha>}"
[[ "$SHA" =~ ^[0-9a-f]{40}$ ]] || { echo "Invalid SHA" >&2; exit 2; }
command -v gh >/dev/null && command -v codex >/dev/null || { echo "gh/codex missing" >&2; exit 2; }
ROOT="$HOME/.local/share/aiops2-codex-dispatch"
STATE="$HOME/.local/state/aiops2-codex-dispatch"
mkdir -p "$ROOT" "$STATE"
chmod 700 "$ROOT" "$STATE"
if [[ ! -d "$ROOT/repo/.git" ]]; then
  gh repo clone "$REPO" "$ROOT/repo" -- --filter=blob:none
fi
git -C "$ROOT/repo" fetch origin "$BRANCH"
git -C "$ROOT/repo" cat-file -e "$SHA^{commit}"
git -C "$ROOT/repo" merge-base --is-ancestor "$SHA" "origin/$BRANCH" || {
  echo "SHA not on expected branch" >&2; exit 2;
}
[[ -z "$(git -C "$ROOT/repo" status --porcelain)" ]] || {
  echo "Refusing dirty dispatch checkout" >&2; exit 2;
}
git -C "$ROOT/repo" checkout --detach "$SHA"
python3 -B -m unittest discover -s "$ROOT/repo/tests" -p test_poll_codex_commands.py -q
cat > "$ROOT/run.sh" <<EOF
#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
/usr/bin/flock -n "$STATE/cron.lock" /usr/bin/python3 -B "$ROOT/repo/ops/coordination/poll_codex_commands.py" --sha "$SHA" --checkout "$ROOT/repo" --state-dir "$STATE"
EOF
chmod 700 "$ROOT/run.sh"
MARK="# AIOPS2_CODEX_DISPATCH_V1"
LINE="*/2 * * * * $ROOT/run.sh >> $STATE/cron.log 2>&1 $MARK"
CURRENT="$(crontab -l 2>/dev/null || true)"
# Replace only our own tagged line; preserve all existing entries byte-for-byte.
{ printf '%s\n' "$CURRENT" | grep -v -F "$MARK" || true; printf '%s\n' "$LINE"; } | crontab -
echo "INSTALLED_PINNED_SHA=$SHA"
echo "CRON=$LINE"
echo "To disable: crontab -e (remove only $MARK)"
