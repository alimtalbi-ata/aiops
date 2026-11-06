import math
from decimal import Decimal
import os
import hmac
import json

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from shared.db import db
from shared.ids import new

router = APIRouter()

INTERNAL_TOKEN = (
    os.getenv("AIOPS_INTERNAL_TOKEN")
    or os.getenv("AIOPS_ADMIN_TOKEN")
)

NODE_ID = "CI-FS-LAB-12M"
FILESYSTEM = "/fs-lab"
SOURCE = "real-fs-lab"
METRIC = "fs_used_percent"
THRESHOLD = 90


class EvidenceObservation(BaseModel):
    evidence_id: str = Field(min_length=1, max_length=256)


def authorize(authorization):
    if not INTERNAL_TOKEN:
        raise HTTPException(503, "internal_auth_not_configured")

    supplied = (authorization or "").removeprefix("Bearer ")

    if not supplied or not hmac.compare_digest(
        supplied, INTERNAL_TOKEN
    ):
        raise HTTPException(401, "invalid_internal_token")


def load_real_evidence(cur, evidence_id):
    cur.execute(
        """
        SELECT evidence_id, source, observed_at,
               provenance, payload
        FROM aiops.evidence
        WHERE evidence_id = %s
        """,
        (evidence_id,),
    )

    row = cur.fetchone()

    if not row:
        raise HTTPException(404, "evidence_not_found")

    eid, source, observed_at, provenance, payload = row

    if source != SOURCE:
        raise HTTPException(422, "invalid_evidence_source")

    if not isinstance(provenance, dict):
        raise HTTPException(422, "invalid_evidence_provenance")

    if not isinstance(payload, dict):
        raise HTTPException(422, "invalid_evidence_payload")

    if provenance.get("synthetic") is not False:
        raise HTTPException(422, "synthetic_evidence_rejected")

    if payload.get("synthetic") is not False:
        raise HTTPException(422, "synthetic_measurement_rejected")

    run_id = provenance.get("run_id")

    if not isinstance(run_id, str) or not run_id.startswith("RUN-"):
        raise HTTPException(422, "invalid_run_id")

    if payload.get("run_id") != run_id:
        raise HTTPException(422, "evidence_run_mismatch")

    if payload.get("filesystem") != FILESYSTEM:
        raise HTTPException(422, "invalid_filesystem")

    if payload.get("target_ci_id") != NODE_ID:
        raise HTTPException(422, "invalid_target_ci")

    usage = payload.get("used_percent")

    if type(usage) is not int or not 0 <= usage <= 100:
        raise HTTPException(422, "invalid_filesystem_measurement")

    if payload.get("threshold_percent") != THRESHOLD:
        raise HTTPException(422, "invalid_threshold")

    if payload.get("alert_firing") is not (usage >= THRESHOLD):
        raise HTTPException(422, "inconsistent_alert_state")

    if observed_at is None:
        raise HTTPException(422, "missing_observation_timestamp")

    return {
        "evidence_id": eid,
        "run_id": run_id,
        "observed_at": observed_at,
        "used_percent": usage,
        "alert_firing": usage >= THRESHOLD,
    }


@router.post("/api/twin/observations")
def ingest_observation(
    request: EvidenceObservation,
    authorization: str | None = Header(default=None),
):
    authorize(authorization)

    with db() as conn:
        with conn.cursor() as cur:
            evidence = load_real_evidence(
                cur, request.evidence_id
            )

            cur.execute(
                """
                SELECT 1
                FROM aiops.twin_nodes
                WHERE node_id = %s
                """,
                (NODE_ID,),
            )

            if not cur.fetchone():
                raise HTTPException(409, "filesystem_node_not_provisioned")

            observation_id = new("OBS")

            payload = {
                "source": SOURCE,
                "synthetic": False,
                "run_id": evidence["run_id"],
                "filesystem": FILESYSTEM,
                "used_percent": evidence["used_percent"],
                "threshold_percent": THRESHOLD,
                "alert_firing": evidence["alert_firing"],
            }

            cur.execute(
                """
                INSERT INTO aiops.observations (
                    observation_id,
                    node_id,
                    metric,
                    value,
                    unit,
                    observed_at,
                    status,
                    evidence_id,
                    payload
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                ON CONFLICT (evidence_id)
                WHERE evidence_id IS NOT NULL
                DO NOTHING
                RETURNING observation_id
                """,
                (
                    observation_id,
                    NODE_ID,
                    METRIC,
                    evidence["used_percent"],
                    "percent",
                    evidence["observed_at"],
                    "CRITICAL" if evidence["alert_firing"] else "OK",
                    evidence["evidence_id"],
                    json.dumps(payload),
                ),
            )

            inserted = cur.fetchone()

            if inserted:
                result_id = inserted[0]
                deduplicated = False
            else:
                cur.execute(
                    """
                    SELECT observation_id
                    FROM aiops.observations
                    WHERE evidence_id = %s
                    """,
                    (evidence["evidence_id"],),
                )
                existing = cur.fetchone()

                if not existing:
                    raise HTTPException(
                        503, "observation_persistence_failed"
                    )

                result_id = existing[0]
                deduplicated = True

    return {
        "status": "PASS",
        "observation_id": result_id,
        "evidence_id": evidence["evidence_id"],
        "node_id": NODE_ID,
        "used_percent": evidence["used_percent"],
        "alert_firing": evidence["alert_firing"],
        "synthetic": False,
        "deduplicated": deduplicated,
    }


def _validated_fs_percent(value):
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise ValueError('invalid_observation_value')
    numeric_value = float(value)
    if not math.isfinite(numeric_value) or not 0 <= numeric_value <= 100:
        raise ValueError('invalid_observation_value')
    return numeric_value


@router.get(
    "/api/twin/fs-lab/metrics",
    response_class=PlainTextResponse,
)
def fs_lab_metrics():
    with db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT value, observed_at, payload
                FROM aiops.observations
                WHERE node_id = %s
                  AND metric = %s
                  AND payload->>'synthetic' = 'false'
                ORDER BY observed_at DESC, known_at DESC
                LIMIT 1
                """,
                (NODE_ID, METRIC),
            )
            row = cur.fetchone()

    if not row:
        return PlainTextResponse(
            "",
            media_type="text/plain; version=0.0.4",
        )

    value, observed_at, payload = row

    if observed_at is None:
        raise HTTPException(503, "observation_timestamp_missing")

    if not isinstance(payload, dict):
        raise HTTPException(503, "invalid_observation_payload")

    try:
        numeric_value = _validated_fs_percent(value)
    except (TypeError, ValueError, OverflowError):
        raise HTTPException(503, "invalid_observation_value")

    firing = 1 if numeric_value >= THRESHOLD else 0

    labels = (
        '{filesystem="/fs-lab",'
        'ci="CI-FS-LAB-12M"}'
    )

    timestamp = observed_at.timestamp()

    body = (
        "# HELP aiops_twin_fs_lab_used_percent "
        "Filesystem usage percentage\n"
        "# TYPE aiops_twin_fs_lab_used_percent gauge\n"
        f"aiops_twin_fs_lab_used_percent{labels} {numeric_value}\n"
        "# HELP aiops_twin_fs_lab_alert_firing "
        "Filesystem threshold alert state\n"
        "# TYPE aiops_twin_fs_lab_alert_firing gauge\n"
        f"aiops_twin_fs_lab_alert_firing{labels} {firing}\n"
        "# HELP aiops_twin_fs_lab_observation_timestamp_seconds "
        "Original observation timestamp\n"
        "# TYPE aiops_twin_fs_lab_observation_timestamp_seconds gauge\n"
        f"aiops_twin_fs_lab_observation_timestamp_seconds{labels} "
        f"{timestamp}\n"
    )

    return PlainTextResponse(
        body,
        media_type="text/plain; version=0.0.4",
    )
