"""Stage a minimal build context for the existing disposable E17 target.
Build phase only; the eventual installer must consume a verified OCI digest.
No Docker invocation, credentials, checkout mount, or production operation.
"""
import ast
import hashlib
import json
from pathlib import Path
import re
import sys

KIT = ("poc-e17-product-worker-smoke.py", "poc-temporal-e17-smoke.py",
       "poc_temporal_e17_workflow.py", "poc-multiasset-observed.py")
VERTICAL = ("core_ingest", "enterprise_clock", "hitl_demo", "lab_context",
            "recovery_verify", "lab_target_fence", "ingestion_demo", "core_read",
            "ingestion_store", "enterprise_context", "enterprise_activity",
            "enterprise_corpus", "enterprise_knowledge", "enterprise_hybrid",
            "enterprise_case_knowledge", "enterprise_episodes", "enterprise_triage",
            "enterprise_parametric", "enterprise_scenarios", "evidence_retrieval",
            "policy_demo", "rca_preview", "measured_rca", "correlation_demo",
            "vertical_demo", "bounded_http_transport")
def stage(source, out, worker):
    if not re.fullmatch(r"127\.0\.0\.1:15080/aiops-v3/worker@sha256:[a-f0-9]{64}", worker):
        raise ValueError("verified disposable Worker digest reference required")
    if out.exists() or out.is_symlink() or not out.parent.is_dir():
        raise ValueError("fresh build context required")
    paths = [Path("kit") / n for n in KIT] + [Path("vertical") / (n+".py") for n in VERTICAL]
    available = {p.stem for p in (source/"vertical").glob("*.py")}
    included = {p.stem for p in paths}
    files = {}
    for rel in paths:
        p = source/rel
        if not p.is_file() or p.resolve() != p.absolute():
            raise ValueError("missing or linked source: "+str(rel))
        raw = p.read_bytes()
        for node in ast.walk(ast.parse(raw, filename=str(rel))):
            names = ([node.module] if isinstance(node, ast.ImportFrom) else
                     [a.name for a in node.names] if isinstance(node, ast.Import) else [])
            for name in names:
                if name and name.split(".")[0] in available - included:
                    raise ValueError("unreviewed local dependency: "+name)
        files[rel.as_posix()] = raw
    out.mkdir(mode=0o700)
    for name, raw in files.items():
        dest = out/name
        dest.parent.mkdir(exist_ok=True)
        dest.write_bytes(raw)
    dockerfile = ("FROM "+worker+"\n"
                  "COPY --chown=1000:1000 kit/ /lab/kit/\n"
                  "COPY --chown=1000:1000 vertical/ /lab/vertical/\n"
                  "ENV PYTHONDONTWRITEBYTECODE=1\n"
                  "USER 1000:1000\n"
                  'ENTRYPOINT ["python", "/lab/kit/poc-e17-product-worker-smoke.py"]\n')
    (out/"Dockerfile").write_text(dockerfile)
    files["Dockerfile"] = dockerfile.encode()
    report = {"classification":"V3_E17_TARGET_BUILD_CONTEXT", "worker_base":worker,
              "files":{name:hashlib.sha256(raw).hexdigest() for name,raw in sorted(files.items())},
              "production_authorized":False,"runtime":"NOT_RUN"}
    print(json.dumps(report,sort_keys=True))
    return report

if __name__ == "__main__":
    if len(sys.argv)!=4:
        raise SystemExit("stage-e17-target.py V3_SPIKE NEW_CONTEXT WORKER_DIGEST")
    stage(Path(sys.argv[1]),Path(sys.argv[2]),sys.argv[3])
