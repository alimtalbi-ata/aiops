import hashlib
import json
import logging
import os
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

CORE = os.environ.get(
    "CORE_URL", "http://aiops2-core:810"
)
WORKER = os.environ.get(
    "WORKER_URL", "http://aiops2-worker:815"
)
TOKEN = os.environ.get("AIOPS_ADMIN_TOKEN", "")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)

def post(url, payload, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as response:
        return json.load(response)

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != "/health":
            self.send_error(404)
            return
        self.reply(200, {"status": "ok"})

    def do_POST(self):
        if self.path != "/alertmanager":
            self.send_error(404)
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length < 1 or length > 100000:
                self.reply(413, {"error": "invalid_length"})
                return

            body = json.loads(self.rfile.read(length))
            results = []

            for alert in body.get("alerts", []):
                labels = alert.get("labels", {})

                # Only explicitly tagged FS385 test alerts.
                if labels.get("aiops_test") != "FS385":
                    results.append({"status": "ignored"})
                    continue

                if alert.get("status") != "firing":
                    results.append({"status": "ignored_resolved"})
                    continue

                if labels.get("filesystem") != "/fs-lab":
                    results.append({"status": "ignored_target"})
                    continue

                if not TOKEN:
                    raise RuntimeError("internal_token_missing")

                fingerprint = hashlib.sha256(
                    json.dumps(
                        {
                            "labels": labels,
                            "startsAt": alert.get("startsAt"),
                        },
                        sort_keys=True,
                    ).encode()
                ).hexdigest()[:16].upper()

                external_id = "FS385-AM-" + fingerprint

                incident = post(
                    CORE + "/api/incidents",
                    {
                        "external_id": external_id,
                        "title": (
                            "[FS385] Filesystem /fs-lab "
                            "— canal Alertmanager"
                        ),
                        "severity": "P2",
                        "service_id": "CI-FS-LAB-12M",
                        "source": "alertmanager",
                        "synthetic": True,
                        "payload": {
                            "alert_fingerprint": fingerprint,
                            "labels": labels,
                            "startsAt": alert.get("startsAt"),
                            "test": "FS385",
                            "remediation_authorized": False,
                        },
                    },
                    TOKEN,
                )

                incident_id = incident.get("incident_id")
                if not incident_id:
                    raise RuntimeError("incident_id_missing")

                run = post(
                    CORE + "/api/runs",
                    {
                        "mode": "DEMO",
                        "scenario_id": "SCN-FS-REAL-FULL",
                        "incident_id": incident_id,
                        "idempotency_key": "FS385-" + fingerprint,
                    },
                    TOKEN,
                )

                run_id = run.get("run_id")
                if not run_id:
                    raise RuntimeError("run_id_missing")

                workflow = post(
                    WORKER + "/api/execution/start",
                    {
                        "version": run["version"],
                        "run_id": run_id,
                        "mode": "DEMO",
                        "scenario_id": "SCN-FS-REAL-FULL",
                    },
                    TOKEN,
                )

                logging.info(
                    "FS385 incident=%s run=%s workflow=%s",
                    incident_id,
                    run_id,
                    workflow.get("workflow_id"),
                )

                results.append({
                    "incident_id": incident_id,
                    "run_id": run_id,
                    "workflow_id": workflow.get("workflow_id"),
                    "status": "submitted",
                })

            self.reply(200, {"results": results})

        except Exception as exc:
            logging.exception("FS385 ingestion failed")
            self.reply(500, {
                "error": type(exc).__name__
            })

    def reply(self, code, data):
        payload = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

ThreadingHTTPServer(
    ("0.0.0.0", 8185), Handler
).serve_forever()
