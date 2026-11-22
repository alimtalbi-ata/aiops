from pathlib import Path
"""Activité Temporal pour l'investigation du FS de démonstration."""
from worker.fs_lab_evidence import build_fs_evidence

import json
import os
import subprocess

from temporalio import activity


@activity.defn(name="fs_lab_inspect")
async def fs_lab_inspect(args: dict) -> dict:
    # AIOPS2_FS_BRIDGE_CLIENT_V30
    import asyncio
    import urllib.request

    run_id = str(args.get("run_id", ""))
    if not run_id.startswith("RUN-"):
        raise ValueError("invalid_run_id")

    # FS40_UNIX_BRIDGE_CLIENT
    import http.client
    import socket

    unix_socket = os.environ.get("AIOPS_FS_BRIDGE_UNIX_SOCKET", "")
    url = os.environ.get("AIOPS_FS_BRIDGE_URL", "")
    # FS45_TOKEN_FILE_SUPPORT
    token_file = os.environ.get("AIOPS_FS_BRIDGE_TOKEN_FILE", "")
    if token_file:
        token = Path(token_file).read_text(encoding="utf-8").strip()
    else:
        token = os.environ.get("AIOPS_FS_BRIDGE_TOKEN", "")

    if len(token) < 32:
        raise RuntimeError("fs_bridge_not_configured")
    if not unix_socket and not url.startswith("http://"):
        raise RuntimeError("fs_bridge_transport_not_configured")

    def inspect():
        body = json.dumps({"action": "inspect"}).encode()
        headers = {
            "Authorization": "Bearer " + token,
            "Content-Type": "application/json",
        }

        if unix_socket:
            class UnixConnection(http.client.HTTPConnection):
                def connect(self):
                    self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                    self.sock.settimeout(self.timeout)
                    self.sock.connect(unix_socket)

            connection = UnixConnection("localhost", timeout=30)
            try:
                connection.request("POST", "/execute", body=body, headers=headers)
                response = connection.getresponse()
                if response.status != 200:
                    raise RuntimeError("fs_bridge_inspection_failed")
                return json.loads(response.read())
            finally:
                connection.close()

        request = urllib.request.Request(
            url.rstrip("/") + "/execute",
            data=body,
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            if response.status != 200:
                raise RuntimeError("fs_bridge_inspection_failed")
            return json.load(response)

    payload = await asyncio.to_thread(inspect)

    if not isinstance(payload, dict) or payload.get("status") != "SUCCESS":
        raise RuntimeError("fs_bridge_invalid_response")

    inspection = {
        "run_id": run_id,
        "source": "REAL_FS_LAB",
        "filesystem": "/fs-lab",
        "inspection": payload,
        "read_only": True,
    }

    evidence = build_fs_evidence(run_id, inspection)
    return {**inspection, "evidence": evidence}
