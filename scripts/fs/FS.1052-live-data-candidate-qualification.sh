#!/usr/bin/env bash
set -euo pipefail
echo "FS1052_MODE=TEMPORARY_READ_ONLY_LIVE_DATA"
IMAGE=aiops2-portal:fs1051-visual-candidate
NAME="aiops2-fs1052-qualify-$$"
docker image inspect "$IMAGE" >/dev/null
docker network inspect aiops2-rebuild-integration >/dev/null
docker network inspect aiops2-rebuild-control >/dev/null
cleanup(){ docker rm -f "$NAME" >/dev/null 2>&1 || true; }
trap cleanup EXIT
docker run -d --name "$NAME" --network aiops2-rebuild-integration \
 --read-only --tmpfs /tmp:rw,noexec,nosuid,size=16m \
 --cap-drop ALL --security-opt no-new-privileges \
 -e PYTHONDONTWRITEBYTECODE=1 \
 -e EXPLORER_ENABLED=1 -e EXPLORER_ALLOWED_CIDRS=127.0.0.1/32 \
 -e AIOPS_INTERNAL_TOKEN=fs1052-test-only \
 --entrypoint sleep "$IMAGE" 300 >/dev/null
docker network connect aiops2-rebuild-control "$NAME"
docker exec -i "$NAME" python - <<'PY'
import asyncio, json
from portal.main import app

async def probe(path, ip="127.0.0.1"):
    sent=[]
    delivered=False
    async def receive():
        nonlocal delivered
        if not delivered:
            delivered=True
            return {"type":"http.request","body":b"","more_body":False}
        return {"type":"http.disconnect"}
    async def send(msg):
        sent.append(msg)
    scope={"type":"http","asgi":{"version":"3.0"},"http_version":"1.1",
           "method":"GET","scheme":"http","path":path,"raw_path":path.encode(),
           "root_path":"","query_string":b"",
           "headers":[(b"host",b"localhost")],
           "client":(ip,12345),"server":("localhost",777)}
    await asyncio.wait_for(app(scope,receive,send),timeout=20)
    status=next((m["status"] for m in sent if m["type"]=="http.response.start"),None)
    body=b"".join(m.get("body",b"") for m in sent if m["type"]=="http.response.body")
    return status,body

async def main():
    for path in ("/health","/explorer/databases","/explorer/prometheus","/explorer/cmdb","/api/explorer/catalog","/explorer/visual"):
        status,_=await probe(path)
        print("FS1052_LEGACY_OR_VISUAL="+path+" STATUS="+str(status))
        assert status==200,(path,status)
    for path in ("/api/fs1051/prometheus","/api/fs1051/twin"):
        status,body=await probe(path)
        print("FS1052_LIVE_API="+path+" STATUS="+str(status))
        assert status==200,(path,status,body[:200])
        obj=json.loads(body)
        if path.endswith("prometheus"):
            assert isinstance(obj.get("targets"),list)
            assert isinstance(obj.get("up"),int)
            assert isinstance(obj.get("down"),int)
            assert isinstance(obj.get("total"),int)
            assert obj["total"]>=1
            print("FS1052_PROM_TARGETS="+str(len(obj["targets"])))
            print("FS1052_PROM_UP="+str(obj["up"])+" DOWN="+str(obj["down"])+" TOTAL="+str(obj["total"]))
        else:
            assert isinstance(obj.get("nodes"),list)
            assert isinstance(obj.get("edges"),list)
            assert obj["total_nodes"]>=1
            print("FS1052_TWIN_NODES="+str(obj["total_nodes"])+" EDGES="+str(obj["total_edges"]))
    # Verify the newly exposed endpoints do not bypass the explorer's network policy.
    for path in ("/explorer/visual","/api/fs1051/prometheus","/api/fs1051/twin"):
        status,_=await probe(path,"198.51.100.42")
        print("FS1052_UNTRUSTED="+path+" STATUS="+str(status))
        assert status in (401,403), (path,status)
    print("FS1052_LIVE_DATA=PASS")
    print("FS1052_ACCESS_POLICY=PASS")
    print("FS1052_RESULT=PASS")
asyncio.run(main())
PY
