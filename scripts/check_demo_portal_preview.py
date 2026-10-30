#!/usr/bin/env python3
"""Isolated offline preview of the EXISTING ACME Portal, never a deployment.

Binds loopback only; disables POST and other mutations at the ASGI boundary.
All backend URLs are deliberately unreachable. The six-step business story is
SIMULATED/UNKNOWN/PROJECTED_ONLY, never an observed Core or GLPI run.
Requires the existing app dependencies, including uvicorn; no new service/HTML.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import secrets
import sys


class ReadOnlyPreview:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "websocket":
            await send({"type": "websocket.close", "code": 1008})
            return
        if scope["type"] == "http" and scope.get("method") not in ("GET", "HEAD"):
            await send({"type": "http.response.start", "status": 405,
                        "headers": [(b"content-type", b"text/plain; charset=utf-8"),
                                    (b"cache-control", b"no-store")]})
            await send({"type": "http.response.body", "body": b"read-only preview"})
            return
        await self.app(scope, receive, send)


def isolate_environment(env):
    """Never reuse an operator's production credentials or backend endpoints."""
    env["AIOPS_DEMO_LAUNCH_ENABLED"] = "false"
    env["AIOPS_INTERNAL_TOKEN"] = secrets.token_urlsafe(32)
    env.pop("AIOPS_ADMIN_TOKEN", None)
    for name in ("CORE_URL", "TWIN_URL", "COPILOT_URL", "POLICY_URL"):
        env[name] = "http://127.0.0.1:1"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=17777)
    args = parser.parse_args(argv)
    if not 1024 <= args.port <= 65535:
        parser.error("port must be in 1024..65535")
    isolate_environment(os.environ)
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
    from portal.main import app  # existing application, never a second portal
    import uvicorn
    print(f"OFFLINE_ONLY SIMULATED/UNKNOWN: http://127.0.0.1:{args.port}/demo-studio/business-story", flush=True)
    uvicorn.run(ReadOnlyPreview(app), host="127.0.0.1", port=args.port,
                access_log=False, log_level="warning")
    return 0


if __name__ == "__main__":
    sys.exit(main())
