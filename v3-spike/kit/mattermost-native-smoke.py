"""Native Mattermost smoke, fresh disposable server only."""
import json
import os
import re
import secrets
import urllib.request
import urllib.error

port=int(os.environ["MM_LAB_PORT"])
if not 1024<=port<=65535 or port in (7770,7777,7790):
    raise ValueError("invalid lab port")
base=f"http://127.0.0.1:{port}/api/v4"
token=None
def call(method,path,data=None):
    headers={"Content-Type":"application/json"}
    if token: headers["Authorization"]="Bearer "+token
    req=urllib.request.Request(base+path,data=None if data is None else json.dumps(data).encode(),headers=headers,method=method)
    try:
        with urllib.request.urlopen(req,timeout=30) as response:
            return json.loads(response.read()),response.headers
    except urllib.error.HTTPError as exc:
        error=json.loads(exc.read(8192))
        print("Mattermost API error:",exc.code,error.get("id","unknown"))
        raise
if os.environ.get("MM_LAB_EXECUTE")=="1":
    with open(os.environ["MM_LAB_BINDING_FILE"]) as f:
        binding=json.load(f)
    token=binding["auth"]
    result,_=call("POST","/commands/execute",{"channel_id":binding["channel_id"],"team_id":binding["team_id"],"command":"/aiops incident"})
    assert result["response_type"]=="ephemeral",result
    assert all(x in result["text"] for x in ("UNKNOWN","DENY"))
    if os.environ.get("MM_LAB_BACKEND_MODE","mock")=="real":
        with open(os.path.join(os.environ["MM_LAB_BINDING_DIR"],"expected.json")) as f:
            expected=json.load(f)
        assert "MOCK BACKEND" not in result["text"]
        assert expected["incident_id"] in result["text"] and expected["run_id"] in result["text"]
        assert expected["sources"] and all(e["evidence_id"] in result["text"] and e["payload_hash"] in result["text"] for e in expected["sources"])
    else:
        assert "MOCK BACKEND" in result["text"]
    print("Native slash command response verified")
    raise SystemExit(0)
password=secrets.token_urlsafe(24)+"Aa1!"
user={"email":"operator@example.invalid","username":"laboperator","password":password}
call("POST","/users",user)
me,headers=call("POST","/users/login",{"login_id":user["email"],"password":password})
token=headers["Token"]
team,_=call("POST","/teams",{"name":"aiops-lab","display_name":"AIOPS synthetic lab","type":"O"})
channel,_=call("POST","/channels",{"team_id":team["id"],"name":"incident-lab","display_name":"Incident lab","type":"O"})
url=os.environ["MM_LAB_COMMAND_URL"]
if not re.fullmatch(r"http://[a-z0-9-]+:[0-9]+/api/v1/mattermost/command",url):
    raise ValueError("invalid lab callback")
command,_=call("POST","/commands",{"team_id":team["id"],"trigger":"aiops","method":"P","url":url,"display_name":"AIOPS lab"})
# Callback receiver must be configured with the generated command token and channel.
# Emit only to a caller-owned 0600 file, never stdout.
path=os.environ["MM_LAB_BINDING_FILE"]
fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
with os.fdopen(fd,"w") as f:
    json.dump({"token":command["token"],"channel_id":channel["id"],"team_id":team["id"],"auth":token},f)
print("Native Mattermost user/team/channel/command created")
