"""FS147 optional strict bridge evidence gate; transport authenticity remains host-owned.

Require structured command records, not merely a self-declared commands list.
No shell execution or filesystem mutation is performed here.
"""
from collections.abc import Mapping
from datetime import datetime, timezone
import hashlib


def attest_bridge_measurement(response):
    """Reject incomplete or internally contradictory read-only fs-lab evidence.

    The authenticated bridge must sign/bind the response at the transport layer;
    this function checks shape and consistency, not remote authenticity.
    """
    if not isinstance(response, Mapping):
        raise ValueError("missing bridge evidence")
    if response.get("source") != "fs-lab-bridge-readonly" or response.get("filesystem") != "/fs-lab":
        raise ValueError("wrong bridge provenance")
    if response.get("read_only") is not True or response.get("commands") != ["df", "du", "ls"]:
        raise ValueError("non-readonly or incomplete command set")
    records = response.get("command_results")
    if not isinstance(records, Mapping) or set(records) != {"df", "du", "ls"}:
        raise ValueError("missing command results")
    digests = []
    for name in ("df", "du", "ls"):
        record = records[name]
        if not isinstance(record, Mapping) or type(record.get("exit_code")) is not int or record["exit_code"] != 0:
            raise ValueError("command failed or unknown: " + name)
        output = record.get("stdout")
        if not isinstance(output, str) or not output.strip() or len(output) > 65536:
            raise ValueError("empty or oversized command output: " + name)
        if record.get("stderr") not in ("", None):
            raise ValueError("unexpected stderr: " + name)
        digests.append(hashlib.sha256(output.encode("utf-8")).hexdigest())
    if "/fs-lab" not in records["df"]["stdout"] or "/fs-lab" not in records["du"]["stdout"]:
        raise ValueError("filesystem absent from measurement")
    if type(response.get("used_percent")) not in (int, float):
        raise ValueError("missing usage percentage")
    from math import isfinite
    if not isfinite(response["used_percent"]) or not 0 <= response["used_percent"] <= 100:
        raise ValueError("invalid usage percentage")
    timestamp = response.get("collected_at")
    if not isinstance(timestamp, str):
        raise ValueError("missing collection time")
    try:
        instant = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        if instant.tzinfo is None or instant.utcoffset() is None:
            raise ValueError("naive collection time")
        instant.astimezone(timezone.utc)
    except (ValueError, OverflowError):
        raise ValueError("invalid collection time") from None
    return tuple(digests)
