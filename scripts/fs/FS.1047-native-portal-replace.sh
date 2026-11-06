#!/usr/bin/env bash
# FS.1047 — authorized native Docker portal replacement, with rollback.
set -Eeuo pipefail
OLD=aiops2-rebuild-portal
BASE=aiops2-portal:fs621-explorers-candidate
CAND=aiops2-portal:fs1040-sql-guard-candidate
STAMP="$(date +%Y%m%d-%H%M%S)"
KEEP="aiops2-rebuild-portal-fs1047-rollback-$STAMP"
STAGE="aiops2-rebuild-portal-fs1047-stage-$STAMP"
DIR="$HOME/aiops2-portal-fs1047-backup-$STAMP"
mkdir -m 700 "$DIR"
umask 077
echo "FS1047_BACKUP_DIR=$DIR"
docker image inspect "$CAND" >/dev/null
docker inspect "$OLD" > "$DIR/original-inspect.json"
docker inspect "$OLD" --format '{{.Image}}' > "$DIR/original-image-id.txt"
# Extract only data required to preserve the container; sensitive env stays on disk mode 0600.
python3 - "$DIR" <<'PY'
import json,sys,pathlib
d=json.load(open(sys.argv[1]+"/original-inspect.json"))[0]
c=d["Config"]; h=d["HostConfig"]; n=d["NetworkSettings"]
assert d["Name"]=="/aiops2-rebuild-portal" and d["State"]["Running"]
assert c["Image"]=="aiops2-portal:fs621-explorers-candidate"
assert h["NetworkMode"]=="aiops2-rebuild-public"
assert set(n["Networks"])=={"aiops2-rebuild-public","aiops2-rebuild-control","aiops2-rebuild-integration"}
assert h["PortBindings"]=={"777/tcp":[{"HostIp":"","HostPort":"7777"}]}
assert h["RestartPolicy"]["Name"]=="unless-stopped"
assert not h.get("Privileged") and not h.get("ReadonlyRootfs")
assert not h.get("Devices") and not h.get("ExtraHosts") and not h.get("Dns")
assert not h.get("CapAdd") and not h.get("CapDrop") and not h.get("SecurityOpt")
assert not c.get("Entrypoint") and not c.get("User")
assert len(d.get("Mounts") or [])==2
assert {m["Destination"] for m in d["Mounts"]}=={"/data/fs-demo","/var/lib/aiops-fs-demo"}
assert all(m["Type"]=="volume" and m["RW"] for m in d["Mounts"])
assert all(not x or ("\n" not in x and "\r" not in x) for x in c["Env"])
assert all("=" in x and not x.startswith("=") for x in c["Env"])
assert not h.get("AutoRemove")
assert not h.get("Binds") or all(isinstance(x,str) for x in h["Binds"])
assert not c.get("Healthcheck")
p=pathlib.Path(sys.argv[1])
(p/"env.list").write_text("\n".join(c["Env"])+"\n")
(p/"expected.json").write_text(json.dumps({"cmd":c.get("Cmd"),"workdir":c.get("WorkingDir"),"networks":sorted(n["Networks"])}))
PY
chmod 600 "$DIR"/*
# Image command and workdir must be identical to original. Abort on drift.
python3 - "$DIR" "$CAND" <<'PY'
import json,sys,subprocess
d=json.loads(subprocess.check_output(["docker","image","inspect",sys.argv[2]]))[0]["Config"]
e=json.load(open(sys.argv[1]+"/expected.json"))
assert d.get("Cmd")==e["cmd"], "candidate image CMD differs"
assert d.get("WorkingDir")==e["workdir"], "candidate image workdir differs"
PY
# The candidate can be staged without opening any port or starting it.
docker create --name "$STAGE" --network aiops2-rebuild-public \
  --volumes-from "$OLD" --env-file "$DIR/env.list" \
  --restart unless-stopped -p 7777:777 "$CAND" >/dev/null
echo "FS1047_PREFLIGHT=PASS"
switched=0
success=0
rollback() {
 local rc=$?
 trap - ERR EXIT
 if (( success )); then return; fi
 if (( switched )); then
  echo "FS1047_ROLLBACK=START"
  if docker inspect "$KEEP" >/dev/null 2>&1; then
   docker stop -t 15 "$OLD" >/dev/null 2>&1 || true
   docker rm -f "$OLD" >/dev/null 2>&1 || true
   docker rename "$KEEP" "$OLD" || true
   docker start "$OLD" || true
  else
   echo "FS1047_ROLLBACK=ORIGINAL_NOT_RENAMED"
   docker start "$OLD" >/dev/null 2>&1 || true
  fi
  echo "FS1047_ROLLBACK=ATTEMPTED"
 else
  docker rm -f "$STAGE" >/dev/null 2>&1 || true
 fi
 echo "FS1047_DEPLOY=FAIL EXIT=$rc"
}
trap rollback ERR EXIT
# Stop and rename original, preserving its volumes, image and original network endpoints.
docker stop -t 20 "$OLD" >/dev/null
docker rename "$OLD" "$KEEP"
switched=1
docker rename "$STAGE" "$OLD"
docker network connect aiops2-rebuild-control "$OLD"
docker network connect aiops2-rebuild-integration "$OLD"
docker start "$OLD" >/dev/null
# Require all three networks, original mounts and new image, not only an HTTP 200.
if [[ "$(docker inspect "$OLD" --format '{{.Config.Image}}')" != "$CAND" ]]; then
 echo "FS1047_VERIFY=FAIL_IMAGE"; false
fi
for network in aiops2-rebuild-public aiops2-rebuild-control aiops2-rebuild-integration; do
 docker inspect "$OLD" --format '{{json .NetworkSettings.Networks}}' | python3 -c 'import json,sys; assert sys.argv[1] in json.load(sys.stdin)' "$network"
done
for path in /health /explorer/databases /explorer/prometheus /explorer/cmdb /api/explorer/catalog; do
 ok=0
 for i in $(seq 1 15); do
  status="$(curl --noproxy '*' -sS --max-time 3 -o /dev/null -w '%{http_code}' "http://127.0.0.1:7777$path" 2>/dev/null || true)"
  if [[ "$status" == 200 ]]; then ok=1; break; fi
  sleep 2
 done
 echo "FS1047_HTTP=$path STATUS=$status"
 if (( ! ok )); then echo "FS1047_VERIFY=FAIL_HTTP"; false; fi
done
success=1
trap - ERR EXIT
echo "FS1047_DEPLOY=PASS"
echo "FS1047_ROLLBACK_CONTAINER=$KEEP"
echo "FS1047_BACKUP_DIR=$DIR"
