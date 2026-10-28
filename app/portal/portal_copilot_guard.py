"""Read-only Copilot browser boundary; no LLM or LIVE authorization implied."""
from __future__ import annotations

import hmac
import math
import os

from fastapi import HTTPException

HEADERS = {"Cache-Control": "no-store", "Pragma": "no-cache",
           "X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer"}


def _valid_token(value: object) -> bool:
    return (isinstance(value, str) and 32 <= len(value) <= 256
            and value.isascii() and value.isprintable()
            and not any(char.isspace() for char in value))


def require_copilot_reader(authorization: str | None, env=None) -> str:
    """Allow a scoped viewer/operator credential, never an internal service token."""
    env = os.environ if env is None else env
    viewer = env.get("AIOPS_PORTAL_READ_TOKEN", "")
    operator = env.get("AIOPS_PORTAL_OPERATOR_TOKEN", "")
    internal = env.get("AIOPS_INTERNAL_TOKEN", "")
    if (not _valid_token(viewer) or
            (operator and (not _valid_token(operator) or operator == viewer)) or
            viewer == internal or (operator and operator == internal)):
        raise HTTPException(503, "portal_read_auth_not_configured", headers=HEADERS)
    scheme, separator, supplied = (authorization or "").partition(" ")
    if (scheme.lower() != "bearer" or not separator or
            not _valid_token(supplied)):
        raise HTTPException(401, "invalid_portal_read_token",
                            headers={**HEADERS, "WWW-Authenticate": "Bearer"})
    if operator and hmac.compare_digest(supplied, operator):
        return "operator"
    if hmac.compare_digest(supplied, viewer):
        return "viewer"
    raise HTTPException(401, "invalid_portal_read_token",
                        headers={**HEADERS, "WWW-Authenticate": "Bearer"})


def validate_question(payload: object) -> str:
    if (not isinstance(payload, dict) or set(payload) != {"question"}
            or not isinstance(payload.get("question"), str)):
        raise HTTPException(422, "invalid_copilot_request", headers=HEADERS)
    question = payload["question"]
    if not question.strip() or len(question) > 2048 or any(
        ord(char) < 32 and char not in "\n\t" for char in question
    ):
        raise HTTPException(422, "invalid_copilot_request", headers=HEADERS)
    return question


def project_copilot_response(payload: object) -> dict:
    """Bounded allowlist projection: upstream cannot self-attest LIVE or actions."""
    if not isinstance(payload, dict):
        raise ValueError("invalid Copilot response")
    answer = payload.get("answer")
    question = payload.get("question")
    sources = payload.get("sources")
    limitations = payload.get("limitations")
    confidence = payload.get("confidence")
    if (not isinstance(answer, str) or not answer.strip() or len(answer) > 8192
            or not isinstance(question, str) or len(question) > 2048
            or not isinstance(sources, list) or len(sources) > 32
            or not isinstance(limitations, list) or len(limitations) > 32
            or not all(isinstance(s, str) and len(s) <= 256 for s in sources)
            or not all(isinstance(s, str) and len(s) <= 512 for s in limitations)
            or type(confidence) not in (float, int)
            or not math.isfinite(confidence) or not 0 <= confidence <= 1):
        raise ValueError("invalid Copilot response")
    return {"answer": answer, "question": question, "sources": sources,
            "confidence": confidence, "limitations": limitations,
            "provenance": "UNATTESTED_UPSTREAM_API_READ",
            "runtime_authenticated": False,
            "live_remediation_authorized": False,
            "state": "READABLE_UNVERIFIED"}
