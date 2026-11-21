"""Construction de preuves FS réelles pour AIOps2."""

import re


def build_fs_evidence(run_id: str, inspection: dict) -> dict:
    if not re.fullmatch(r"RUN-[A-Za-z0-9-]{1,64}", run_id):
        raise ValueError("invalid_run_id")

    if not isinstance(inspection, dict):
        raise ValueError("invalid_inspection")

    if inspection.get("source") != "REAL_FS_LAB":
        raise ValueError("untrusted_fs_source")

    result = inspection.get("inspection")
    if not isinstance(result, dict) or result.get("status") != "SUCCESS":
        raise ValueError("fs_inspection_not_successful")

    output = result.get("stdout")
    if not isinstance(output, str) or len(output) > 12000:
        raise ValueError("invalid_fs_output")

    match = re.search(
        r"(?m)^tmpfs\s+(\S+)\s+(\S+)\s+(\S+)\s+(\d+)%\s+/fs-lab\s*$",
        output,
    )
    if not match:
        raise ValueError("fs_mount_measurement_missing")

    usage = int(match.group(4))
    if not 0 <= usage <= 100:
        raise ValueError("invalid_fs_usage")

    return {
        "run_id": run_id,
        "source": "REAL_FS_LAB",
        "target_ci_id": "CI-FS-LAB-12M",
        "filesystem": "/fs-lab",
        "used_percent": usage,
        "threshold_percent": 90,
        "alert_firing": usage >= 90,
        "observations": {
            "df_du_ls": output,
        },
        "evidence_kind": "RUNTIME_FILESYSTEM_OBSERVATION",
        "synthetic_measurement": False,
    }
