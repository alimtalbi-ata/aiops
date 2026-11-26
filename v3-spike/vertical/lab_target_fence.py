"""Process-lifetime fence for a single synthetic lab target.

Preparation only: no action, network, Temporal registration or capability.
The target owner must keep ONE instance for its full lifetime, outside the
restorable HITL database. A restarted target must generate a new identity.
This is not a durable execution receipt or a defense against rollback of
the target process itself.
"""
import hashlib
import hmac
import json
import re
import threading
import uuid


class LabTargetFence:
    def __init__(self, *, run_id, incident_id, resource, context_sha256):
        for value, pattern in (
            (run_id, r"RUN-[A-F0-9]{16}"),
            (incident_id, r"INC-CI-INGEST-[a-f0-9]{32}"),
            (resource, r"NODE-CI-[A-Z0-9-]{1,80}"),
            (context_sha256, r"[a-f0-9]{64}"),
        ):
            if not isinstance(value, str) or not re.fullmatch(pattern, value):
                raise ValueError("invalid synthetic target binding")
        self._target_id = uuid.uuid4().hex
        self._binding = {
            "run_id": run_id, "incident_id": incident_id,
            "workflow_id": run_id, "context_sha256": context_sha256,
            "lab_action": {"action": "RESET_LAB_HTTP_DELAY",
                           "resource": resource, "target_id": self._target_id},
        }
        self._lock = threading.Lock()
        self._claimed = False

    def scope(self):
        return dict(self._binding["lab_action"])

    def claim(self, reservation):
        """Accept only a server-verified reservation; claim never executes.

        Hash checks detect inconsistent payloads, not forged authorization.
        A claim with no verified result is permanently ambiguous for this
        target incarnation, including after a HITL database restore.
        """
        if not isinstance(reservation, dict):
            raise ValueError("invalid reservation")
        record = json.loads(json.dumps(reservation))
        disposition = record.pop("disposition", None)
        digest = record.pop("reservation_sha256", None)
        binding = record.get("binding")
        if not isinstance(binding, dict):
            raise ValueError("invalid reservation binding")
        expected = {
            "classification": "SYNTHETIC_LAB_RESERVATION",
            "binding": self._binding | {
                "receipt_id": binding.get("receipt_id"),
                "receipt_sha256": binding.get("receipt_sha256"),
            },
            "operational_decision": "DENY",
            "executed_on_host": False, "production_authorized": False,
            "action_authorized": False,
        }
        canonical = lambda obj: json.dumps(obj, sort_keys=True, separators=(",", ":"))
        if (canonical(record) != canonical(expected)
            or not isinstance(digest, str)
            or not re.fullmatch(r"[a-f0-9]{64}", digest)
            or not hmac.compare_digest(hashlib.sha256(canonical(record).encode()).hexdigest(), digest)
            or not isinstance(binding.get("receipt_id"), str)
            or not re.fullmatch(r"HITL-[a-f0-9]{32}", binding["receipt_id"])
            or not isinstance(binding.get("receipt_sha256"), str)
            or not re.fullmatch(r"[a-f0-9]{64}", binding["receipt_sha256"])
            or disposition not in ("RESERVED_NO_EXECUTION", "ALREADY_RESERVED_BLOCKED")):
            raise ValueError("invalid reservation for target incarnation")
        with self._lock:
            if self._claimed or disposition == "ALREADY_RESERVED_BLOCKED":
                self._claimed = True
                status = "UNKNOWN_BLOCKED"
            else:
                self._claimed = True
                status = "CLAIMED_NO_EXECUTION"
        return {"status": status, "target_id": self._target_id,
                "action_authorized": False, "executed_on_host": False,
                "operational_decision": "DENY", "production_authorized": False}
