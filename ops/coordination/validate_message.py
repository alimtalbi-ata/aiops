#!/usr/bin/env python3
"""Validate AIOps2 coordination messages without executing their payloads."""
import argparse
import datetime as dt
import json
import re
import sys
import uuid
from pathlib import Path

KINDS = frozenset(("TASK_REQUEST", "TASK_ACCEPTED", "HEARTBEAT", "BLOCKED", "ARTIFACT_READY", "TEST_RESULT", "DEPLOY_CANDIDATE", "RUNTIME_RECEIPT", "E2E_RESULT", "APPROVAL_REQUIRED", "TASK_DONE", "TASK_FAILED", "TASK_CANCELLED"))
ROLES = frozenset(("schedule.integration", "schedule.core", "schedule.worker", "schedule.twin", "schedule.portal", "codex.core", "codex.worker", "codex.twin", "codex.portal", "codex.integration", "codex.debian", "github.actions", "debian.reporter"))
SHA = re.compile(r"^[0-9a-f]{40}$")
TOKEN = re.compile(r"^[a-zA-Z0-9._:/-]{1,160}$")
REQUIRED = frozenset(("schema_version", "message_id", "correlation_id", "causation_id", "work_id", "kind", "producer", "target", "created_at", "expires_at", "idempotency_key", "revision", "source", "depends_on", "payload_ref", "evidence_refs", "requires_approval"))

class InvalidMessage(ValueError):
    pass

def utc(value):
    if not isinstance(value, str):
        raise InvalidMessage("timestamp must be string")
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise InvalidMessage("invalid timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != dt.timedelta(0):
        raise InvalidMessage("timestamp must be UTC")
    return parsed

def validate(message):
    if not isinstance(message, dict) or set(message) != REQUIRED:
        raise InvalidMessage("message fields differ from v1 contract")
    if message["schema_version"] != "1.0":
        raise InvalidMessage("unsupported schema version")
    try:
        if str(uuid.UUID(message["message_id"])) != message["message_id"]:
            raise ValueError()
    except (ValueError, TypeError, AttributeError) as exc:
        raise InvalidMessage("invalid message_id UUID") from exc
    for key in ("correlation_id", "work_id", "idempotency_key"):
        if not isinstance(message[key], str) or not TOKEN.fullmatch(message[key]):
            raise InvalidMessage("invalid " + key)
    if message["causation_id"] is not None:
        try:
            uuid.UUID(message["causation_id"])
        except (ValueError, TypeError, AttributeError) as exc:
            raise InvalidMessage("invalid causation_id") from exc
    if message["kind"] not in KINDS:
        raise InvalidMessage("unknown message kind")
    if message["producer"] not in ROLES or message["target"] not in ROLES:
        raise InvalidMessage("unregistered actor")
    created, expires = utc(message["created_at"]), utc(message["expires_at"])
    if expires <= created:
        raise InvalidMessage("expires_at must follow created_at")
    if type(message["revision"]) is not int or message["revision"] < 1:
        raise InvalidMessage("invalid revision")
    source = message["source"]
    if not isinstance(source, dict) or set(source) != {"repo", "ref"} or source["repo"] != "alimtalbi-ata/aiops" or not isinstance(source["ref"], str) or not SHA.fullmatch(source["ref"]):
        raise InvalidMessage("source must identify an exact repo SHA")
    if not isinstance(message["depends_on"], list) or not all(isinstance(x, str) and TOKEN.fullmatch(x) for x in message["depends_on"]) or len(set(message["depends_on"])) != len(message["depends_on"]):
        raise InvalidMessage("invalid dependencies")
    if message["work_id"] in message["depends_on"]:
        raise InvalidMessage("self dependency")
    if not isinstance(message["payload_ref"], str) or not message["payload_ref"].startswith("https://github.com/alimtalbi-ata/aiops/"):
        raise InvalidMessage("payload must reference canonical GitHub")
    if not isinstance(message["evidence_refs"], list) or not all(isinstance(x, str) and x.startswith("https://github.com/alimtalbi-ata/aiops/") for x in message["evidence_refs"]):
        raise InvalidMessage("invalid evidence references")
    if type(message["requires_approval"]) is not bool:
        raise InvalidMessage("invalid approval flag")
    if message["kind"] == "DEPLOY_CANDIDATE" and not message["requires_approval"]:
        raise InvalidMessage("deployment candidate requires approval")
    return message

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("messages", nargs="+", type=Path)
    args = parser.parse_args()
    failed = False
    for path in args.messages:
        try:
            validate(json.loads(path.read_text(encoding="utf-8")))
            print(f"VALID {path}")
        except (InvalidMessage, OSError, ValueError) as exc:
            failed = True
            print(f"INVALID {path}: {exc}", file=sys.stderr)
    return int(failed)

if __name__ == "__main__":
    sys.exit(main())
