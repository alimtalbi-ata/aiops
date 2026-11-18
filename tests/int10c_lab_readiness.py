"""Pure test-only readiness gate. No provisioning, network or service startup."""
import re
from pathlib import PurePosixPath

_SHA = re.compile(r"[0-9a-f]{40}\Z")
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")
_RUN = re.compile(r"ci-[a-z0-9]{12,48}\Z")
_KEYS = {"c_sha","b_sha","run_id","postgres_image","temporal_image",
         "worker_image","database","queue","workflow","directory",
         "synthetic_only","external_egress","external_credentials",
         "timeout_seconds"}

def validate_plan(plan, *, expected_c_sha, expected_b_sha):
    """Validate declarative candidate; never grant launch authorization."""
    if type(plan) is not dict or set(plan) != _KEYS:
        raise ValueError("plan_shape")
    for key,expected in (("c_sha",expected_c_sha),("b_sha",expected_b_sha)):
        if type(plan[key]) is not str or not _SHA.fullmatch(plan[key]) or plan[key] != expected:
            raise ValueError("sha_binding")
    run = plan["run_id"]
    if type(run) is not str or not _RUN.fullmatch(run):
        raise ValueError("run_scope")
    if any(type(plan[k]) is not str or not _DIGEST.fullmatch(plan[k])
           for k in ("postgres_image","temporal_image","worker_image")):
        raise ValueError("image_digest")
    if (plan["database"] != run.replace("-","_") or plan["queue"] != run+"-queue"
            or plan["workflow"] != run+"-workflow"
            or plan["directory"] != str(PurePosixPath("/tmp") / run)):
        raise ValueError("resource_scope")
    if (plan["synthetic_only"] is not True or plan["external_egress"] is not False
            or plan["external_credentials"] is not False):
        raise ValueError("isolation")
    if type(plan["timeout_seconds"]) is not int or not 1 <= plan["timeout_seconds"] <= 900:
        raise ValueError("lifecycle_bound")
    return {"status":"PLAN_ONLY","launch_authorized":False,
            "runtime_attested":False,"ownership":"UNKNOWN"}
