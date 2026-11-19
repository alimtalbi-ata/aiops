#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
export DOCKER_HOST="unix:///run/user/$(id -u)/docker.sock"
test "$#" = 3
WORK="$1"
BIND="$2"
CLIENT="$3"
POC=aiops2-poc02
test -s "$WORK/viewer.secret"
test -s "$WORK/artifacts/dist/index.html"
curl -fsS http://127.0.0.1:7790/health >/dev/null
python3 - "$WORK" "$BIND" "$CLIENT" <<'PY'
import ipaddress,pathlib,sys
work=pathlib.Path(sys.argv[1])
bind,client=[str(ipaddress.IPv4Address(x)) for x in sys.argv[2:]]
for x in (bind,client):
    a=ipaddress.ip_address(x)
    if a.is_unspecified or a.is_multicast or a.is_loopback:
        raise SystemExit("Explicit LAN addresses required")
p=work/"server.py"
s=p.read_text()
old='http.server.ThreadingHTTPServer(\n    ("127.0.0.1",7790),Handler\n).serve_forever()'
if s.count(old)!=1 or s.count("    def do_GET(self):")!=1:
    raise SystemExit("Unexpected source; no changes")
s=s.replace("    def do_GET(self):",f'''    def parse_request(self):
        if not super().parse_request():
            return False
        if self.client_address[0] not in ("127.0.0.1", {client!r}):
            self.send_error(403)
            return False
        if self.headers.get("Host") not in ("127.0.0.1:7790", {bind+":7790"!r}):
            self.send_error(403)
            return False
        return True

    def do_GET(self):''')
s=s.replace(old,f'''import threading
local=http.server.ThreadingHTTPServer(("127.0.0.1",7790),Handler)
lan=http.server.ThreadingHTTPServer(({bind!r},7790),Handler)
threading.Thread(target=local.serve_forever,daemon=True).start()
lan.serve_forever()''')
compile(s,str(p),"exec")
backup=work/"server.loopback.py"
if backup.exists():
    raise SystemExit("Backup already exists; stop and inspect")
backup.write_text(p.read_text())
p.write_text(s)
PY
rollback() {
    cat "$WORK/server.loopback.py" > "$WORK/server.py"
    docker restart "$POC" >/dev/null
    echo "POC02_ACCESS_ROLLED_BACK"
}
trap rollback ERR
docker restart "$POC" >/dev/null
for i in $(seq 1 20); do
    curl -fsS --max-time 2 http://127.0.0.1:7790/health >/dev/null 2>&1 && break
    sleep 1
done
curl -fsS http://127.0.0.1:7790/health
echo
curl -fsS -H 'Authorization: Bearer poc-local' http://127.0.0.1:7790/api/mission-actions/journey -o /dev/null
curl -fsS http://127.0.0.1:7788/health >/dev/null
curl -fsS http://127.0.0.1:7789/health >/dev/null
ss -ltnH 'sport = :7790' | grep -F "$BIND:7790"
trap - ERR
echo "POC02_LOCAL_SMOKE=PASS"
echo "POC02_URL=http://$BIND:7790/"
echo "REMOTE_BROWSER=NOT_RUN"
