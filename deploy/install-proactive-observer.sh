#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
[[ "$(id -un)" == aiops && "$(hostname -s | tr '[:upper:]' '[:lower:]')" == srv-deb-05 ]]
sha="${1:?Expected reviewed commit SHA}"
[[ "$sha" =~ ^[0-9a-f]{40}$ ]]
root="$HOME/.local/share/aiops2-proactive"
state="$HOME/.local/state/aiops2-proactive"
mkdir -p "$root" "$state"
exec 9>"$state/install.lock"
flock -n 9
tmp="$(mktemp -d "$root/.stage.XXXXXXXX")"
trap 'rm -rf "$tmp"' EXIT
for f in proactive_candidate.py proactive_watchdog.py; do
  gh api --method GET -H 'Accept: application/vnd.github.raw+json' "repos/alimtalbi-ata/aiops/contents/deploy/$f?ref=$sha" > "$tmp/$f"
done
python3 -m py_compile "$tmp/"*.py
rm -rf "$tmp/__pycache__"
if [[ ! -d "$root/$sha" ]]; then mv "$tmp" "$root/$sha"; fi
python3 "$root/$sha/proactive_candidate.py"
python3 - "$state/candidate.json" <<'PY'
import json,sys
d=json.load(open(sys.argv[1]))
assert d["state"] in {"BUILD_ELIGIBLE","CI_PENDING","CI_BLOCKED","INELIGIBLE"}
assert d["deploy_authorized"] is False
PY
old="$(mktemp "$state/crontab.XXXXXXXX")"
if ! crontab -l > "$old"; then echo "Cannot read existing crontab" >&2; exit 1; fi
new="$(mktemp "$state/crontab-new.XXXXXXXX")"
grep -v '# AIOPS2_PROACTIVE_OBSERVER_V1$' "$old" > "$new" || [[ $? == 1 ]]
printf '%s\n' "* * * * * /usr/bin/python3 -B $root/$sha/proactive_candidate.py >> $state/discovery.log 2>&1 # AIOPS2_PROACTIVE_OBSERVER_V1" "*/2 * * * * /usr/bin/python3 -B $root/$sha/proactive_watchdog.py >> $state/watchdog.log 2>&1 # AIOPS2_PROACTIVE_OBSERVER_V1" >> "$new"
crontab "$new"
echo "Observer installed at $sha; backup=$old; no deployment enabled"
