#!/usr/bin/env bash
# FS.1046: inspect Docker-native recreation feasibility without exposing env values.
set -euo pipefail
echo "FS1046_MODE=READ_ONLY_NATIVE_RECREATE_PREFLIGHT"
docker inspect aiops2-rebuild-portal | python3 -c '
import json,sys
d=json.load(sys.stdin)[0]; c=d["Config"]; h=d["HostConfig"]; n=d["NetworkSettings"]
def flag(k,v): print(k+"="+str(v))
flag("NAME",d["Name"]);flag("IMAGE",c.get("Image"))
flag("STATE",(d.get("State") or {}).get("Status"))
flag("ENTRYPOINT_PRESENT",bool(c.get("Entrypoint")))
flag("CMD_PRESENT",bool(c.get("Cmd")))
flag("WORKDIR_PRESENT",bool(c.get("WorkingDir")))
flag("USER_PRESENT",bool(c.get("User")))
flag("ENV_COUNT",len(c.get("Env") or []))
flag("LABEL_COUNT",len(c.get("Labels") or {}))
flag("RESTART_POLICY",h.get("RestartPolicy"))
flag("AUTO_REMOVE",h.get("AutoRemove"))
flag("PRIVILEGED",h.get("Privileged"))
flag("READONLY_ROOTFS",h.get("ReadonlyRootfs"))
flag("CAP_ADD",h.get("CapAdd"))
flag("CAP_DROP",h.get("CapDrop"))
flag("SECURITY_OPT",h.get("SecurityOpt"))
flag("PID_MODE",h.get("PidMode"))
flag("IPC_MODE",h.get("IpcMode"))
flag("USERNS_MODE",h.get("UsernsMode"))
flag("NETWORK_MODE",h.get("NetworkMode"))
flag("PORT_BINDINGS",h.get("PortBindings"))
flag("EXTRA_HOSTS_PRESENT",bool(h.get("ExtraHosts")))
flag("DNS_PRESENT",bool(h.get("Dns")))
flag("DEVICES_PRESENT",bool(h.get("Devices")))
flag("BINDS_PRESENT",bool(h.get("Binds")))
flag("MOUNT_COUNT",len(d.get("Mounts") or []))
for m in d.get("Mounts") or []:
 flag("MOUNT",{"Type":m.get("Type"),"Name":m.get("Name"),"Destination":m.get("Destination"),"RW":m.get("RW")})
for k,v in sorted((n.get("Networks") or {}).items()):
 flag("NETWORK",{"Name":k,"Aliases":v.get("Aliases"),"IPAMConfig":v.get("IPAMConfig")})
flag("HEALTHCHECK_PRESENT",bool(c.get("Healthcheck")))
flag("LOG_DRIVER",(h.get("LogConfig") or {}).get("Type"))
flag("STOP_SIGNAL",c.get("StopSignal"))
flag("STOP_TIMEOUT",h.get("StopTimeout"))
print("FS1046_PREFLIGHT_DISCOVERY=COMPLETE")
'
