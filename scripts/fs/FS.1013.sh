#!/usr/bin/env bash
set -euo pipefail
echo '===== FS.1013 | DEPLOYMENT AND ROLLBACK READINESS ====='
echo 'MODE=READ_ONLY'
echo 'NO_DEPLOYMENT=YES'
for name in aiops2-rebuild-twin aiops2-rebuild-core aiops2-rebuild-prometheus; do
  echo "===== CONTAINER $name ====="
  docker inspect "$name" | python3 -c '
import json,sys
d=json.load(sys.stdin)[0]; c=d.get("Config") or {}; h=d.get("HostConfig") or {}
n=d.get("NetworkSettings") or {}; labels=c.get("Labels") or {}
print("NAME="+str(d.get("Name")))
print("RUNNING="+str((d.get("State") or {}).get("Running")))
print("IMAGE_REF="+str(c.get("Image")))
print("IMAGE_ID="+str(d.get("Image")))
print("ENTRYPOINT="+repr(c.get("Entrypoint")))
print("CMD="+repr(c.get("Cmd")))
print("WORKDIR="+str(c.get("WorkingDir")))
print("USER="+str(c.get("User")))
print("ENV_KEYS="+",".join(sorted({x.split("=",1)[0] for x in c.get("Env") or []})))
print("EXPOSED_PORT_KEYS="+",".join(sorted((c.get("ExposedPorts") or {}).keys())))
print("PORT_BINDING_KEYS="+",".join(sorted((h.get("PortBindings") or {}).keys())))
print("RESTART_POLICY="+repr(h.get("RestartPolicy")))
print("NETWORK_MODE="+str(h.get("NetworkMode")))
print("PRIVILEGED="+str(h.get("Privileged")))
print("READONLY_ROOTFS="+str(h.get("ReadonlyRootfs")))
print("CAP_ADD="+repr(h.get("CapAdd")))
print("CAP_DROP="+repr(h.get("CapDrop")))
print("SECURITY_OPT="+repr(h.get("SecurityOpt")))
print("PID_MODE="+str(h.get("PidMode")))
print("IPC_MODE="+str(h.get("IpcMode")))
print("SHM_SIZE="+str(h.get("ShmSize")))
print("HEALTHCHECK_DEFINED="+str(c.get("Healthcheck") is not None))
print("NETWORK_ATTACHMENTS="+",".join(sorted((n.get("Networks") or {}).keys())))
for network,settings in sorted((n.get("Networks") or {}).items()):
 print("NETWORK="+network+" ALIASES="+repr(settings.get("Aliases"))+" IPV4="+str(settings.get("IPAddress")))
for m in d.get("Mounts") or []:
 print("MOUNT_TYPE="+str(m.get("Type"))+" DEST="+str(m.get("Destination"))+" RW="+str(m.get("RW"))+" SOURCE="+str(m.get("Source")))
for k in ("com.docker.compose.project","com.docker.compose.service","com.docker.compose.project.config_files","com.docker.compose.project.working_dir"):
 print("COMPOSE_"+k+"="+str(labels.get(k,"UNSET")))
'
done
echo '===== COMPOSE FILE PRESENCE ONLY ====='
for path in \
 /home/aiops/aiops-prometheus-image-patch/compose.metrics-cutover.yml \
 /home/aiops/aiops2-patches/fs-core-real-registration/compose.fs-core.override.yml \
 /home/aiops/aiops2-auto-deploy/glpi-ai-ticket-enrichment-e2e/compose.yml \
 /home/aiops/aiops2-patches/portal-v28-integration/delivery/release-20261105T134055Z/compose-v28.override.yml \
 /home/aiops/aiops2-patches/fs-portal-integration/compose-fs-demo.override.yml \
 /home/aiops/aiops2-patches/fs-portal-v30/build/compose-fs-prometheus.override.yml; do
 if [ -f "$path" ]; then
  echo "COMPOSE_FILE_PRESENT=$path"
  sha256sum "$path" | awk '{print "COMPOSE_FILE_SHA256="$1}'
 else
  echo "COMPOSE_FILE_MISSING=$path"
 fi
done
echo '===== IMAGE ROLLBACK AVAILABILITY ====='
for image in aiops2-twin:fs-evidence-20261105 aiops2-core:fs-real-registration-20261105 aiops2-twin:fs1009-decimal-metrics-candidate-20261106; do
 if docker image inspect "$image" >/dev/null 2>&1; then
  docker image inspect "$image" --format 'IMAGE_PRESENT={{.RepoTags}} IMAGE_ID={{.Id}}'
 else
  echo "IMAGE_MISSING=$image"
 fi
done
echo '===== READ-ONLY PROMETHEUS TARGET STATUS ====='
docker exec aiops2-rebuild-prometheus wget -qO- http://127.0.0.1:9090/api/v1/targets | python3 -c '
import json,sys
d=json.load(sys.stdin)
assert d.get("status")=="success"
for t in d.get("data",{}).get("activeTargets",[]):
 job=t.get("labels",{}).get("job")
 if job in ("aiops2-core","aiops2-twin"):
  print("TARGET="+job+" HEALTH="+str(t.get("health"))+" ERROR="+str(t.get("lastError")))
'
echo '===== SAFETY ====='
echo 'CONTAINER_CREATED=NO'
echo 'CONTAINER_STOPPED=NO'
echo 'PRODUCTION_RESTARTED=NO'
echo 'DATABASE_WRITES=0'
echo 'HTTP_WRITES=0'
echo 'ROLLBACK_EXECUTED=NO'
echo 'FS1013_RESULT=INVENTORY_COMPLETE_REVIEW_REQUIRED'
echo '===== END FS.1013 ====='
