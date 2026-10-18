# AIOps 2.0 R5 — offline Debian deliverable
Author: Abdelhalim Talbi. Status: NOT QUALIFIED.

R5 must be compiled and packaged on a Linux build machine with network access and Docker, then copied via SCP as a ZIP to SRV-DEB-05; the target must not invoke Git, pull images or build Python dependencies.

The ZIP must include all application source files, Compose, scripts, documentation, migrations, the exact Docker image archive images/images.tar, images/images.sha256 and qualification tests. The Docker archive is mandatory: a source-only ZIP is not an offline deployment.

Build host:
1. Ensure Compose config validation and static tests are successful.
2. Supply non-placeholder secrets locally in .env (never commit .env).
3. Build application images with Docker Compose and pull only on the build host.
4. Enumerate resolved image names from docker compose --env-file .env config --format json. Assign deterministic image tags for every built application service.
5. Export every resolved image and its transitive layers using docker save -o images/images.tar IMAGE_1 IMAGE_2 ...; then (cd images && sha256sum images.tar > images.sha256).
6. Run bash deploy/package.sh to make the final ZIP and SHA256 sidecar.

Target host:
1. Verify the ZIP SHA256 before extracting.
2. Extract ZIP to /home/aiops/incoming-r5.
3. In the extracted root, run docker load -i images/images.tar.
4. Export AIOPS2_PASSWORD using a local secret (not the sample password). Run AIOPS2_ROOT=/home/aiops/aiops2-r5 bash 00-Deployment/install.sh.
5. Change to /home/aiops/aiops2-r5; run bash 00-Deployment/start.sh.
6. Save full logs, docker compose ps, the schema exit code, Temporal health, synthetic run evidence and SHA256 manifest for the qualification report.

Required coexistence: portal 7777; n8n 15678; GLPI 18080; Prometheus 19090; Grafana 13000; Temporal UI 18088. Internal Temporal 7233 must not be published.

No claim of qualification or Debian functionality is made before the actual deployment test. Stop on errors and preserve pre-existing environments.
