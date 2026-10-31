#!/usr/bin/env python3
"""Conservative, operator-only ACME P0 four-service image transaction.

No SSH, cron installation, database migration, local source overwrite, global
compose, LIVE remediation, or applied.sha write. Default is read-only plan.
The deployed cron poller is NOT wired to this tool; manual host qualification
and a separately approved poller migration are required.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time

SERVICES = {"aiops2-core": "core", "aiops2-twin": "twin",
            "aiops2-policy": "policy", "aiops2-portal": "portal"}
RUNTIME = frozenset({
    "app/core/main.py", "app/core/demo_evidence_read.py",
    "app/twin/main.py", "app/policy/main.py",
    "app/portal/main.py", "app/portal/demo_v2.py",
    "app/portal/demo_ledger_read.py", "app/shared/tenant_scope.py",
    # Exact shared modules are copied by the four application Dockerfiles.
    "app/shared/acme_demo_offline.py", "app/shared/acme_glpi_ticket_read.py",
    "app/shared/acme_noc_glpi_join.py",
    "app/shared/acme_itsm_evidence_link.py", "app/shared/acme_policy_demo_result.py",
    "app/shared/acme_remediation_projection.py", "app/shared/acme_remediation_receipt.py",
    "app/shared/remediation_lab.py",
})
# Operator diagnostics and the offline fixture catalog are NOT in the app build context.
OPERATOR_ONLY = frozenset({
    "tools/find_acme_demo_run.py", "tools/probe_acme_twin_path.py",
    "config/remediation/recipes.v1.json",
})
CONTROL = frozenset({
    ".github/workflows/quality.yml", ".github/workflows/promote-stable.yml",
    "deploy/deploy-demo-studio-v2.sh", "deploy/poll-approved-deploy.sh",
    "deploy/install-approved-cron.sh", "deploy/deploy-acme-p0.py",
    "deploy/init-env.sh",
})
SHA = re.compile(r"[a-f0-9]{40}\Z")
PROJECT = "aiops2-rebuild"
SCHEMA = "aiops.p0-compose-targeted-transaction.v1"


class Refused(RuntimeError):
    pass


def command(*args: str, cwd: Path | None = None) -> str:
    """Never propagate subprocess output or exceptions (may contain secrets)."""
    try:
        p = subprocess.run(args, cwd=cwd, capture_output=True, text=True,
                           timeout=180, check=False)
    except (OSError, subprocess.TimeoutExpired):
        raise Refused("required_command_unavailable") from None
    if p.returncode:
        raise Refused("command_failed:" + str(args[0]) + ":" + str(args[1] if len(args) > 1 else ""))
    return p.stdout


def classify(path: str, status: str) -> str:
    if status not in ("A", "M") or not path or path.startswith("/") or any(ord(c) < 32 for c in path):
        return "BLOCKED"
    if path in RUNTIME:
        return "IMAGE_TRANSPORT"
    if path == "compose.yml":
        return "LIVE_COMPOSE_COMPATIBILITY_REQUIRED"
    if path in CONTROL:
        return "MANUAL_RELEASE_CONTROL_REVIEW"
    if path in OPERATOR_ONLY:
        return "CI_OR_OPERATOR_ONLY"
    if path.startswith("docs/") or path.startswith("tests/") or path.startswith("scripts/check_demo_"):
        return "CI_OR_OPERATOR_ONLY"
    if path in ("README.md", "VERSION", ".gitignore", "config/.env.example"):
        return "REPOSITORY_ONLY"
    return "BLOCKED"


def plan(delivery: Path, stable_sha: str, candidate_sha: str) -> dict:
    if not SHA.fullmatch(stable_sha) or not SHA.fullmatch(candidate_sha) or stable_sha == candidate_sha:
        raise Refused("invalid_release_shas")
    if command("git", "rev-parse", "HEAD", cwd=delivery).strip() != candidate_sha:
        raise Refused("candidate_checkout_mismatch")
    if command("git", "status", "--porcelain", cwd=delivery).strip():
        raise Refused("dirty_delivery_checkout")
    command("git", "merge-base", "--is-ancestor", stable_sha, candidate_sha, cwd=delivery)
    raw = subprocess.run(["git", "diff", "--name-status", "-z", "--no-renames",
                          stable_sha, candidate_sha], cwd=delivery,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
    if raw.returncode or not raw.stdout.endswith(b"\0"):
        raise Refused("git_diff_unavailable")
    parts = raw.stdout[:-1].split(b"\0")
    if len(parts) % 2 or not parts:
        raise Refused("malformed_git_diff")
    matrix = []
    for status, name in zip(parts[::2], parts[1::2]):
        try:
            status_s, path = status.decode("ascii"), name.decode("utf-8")
        except UnicodeError:
            raise Refused("invalid_git_path_encoding") from None
        matrix.append({"path": path, "status": status_s, "transport": classify(path, status_s)})
    unsupported = sorted(x["path"] for x in matrix if x["transport"] == "BLOCKED")
    return {
        "schema": SCHEMA, "candidate_sha": candidate_sha, "stable_sha": stable_sha,
        "assessment": "BLOCKED" if unsupported else "MANUAL_APPROVAL_REQUIRED",
        "overall": "NO_GO", "unsupported_paths": unsupported,
        "module_deployment_matrix": matrix,
        "not_image_transported": sorted(x["path"] for x in matrix
                                       if x["path"] in OPERATOR_ONLY),
        "image_services": list(SERVICES), "live_host": "NOT_TESTED",
        "rollback": "NOT_TESTED", "applied_sha": "NOT_ATTESTED",
        "notes": "No source files or volumes are copied; image build from approved Git checkout only.",
    }


def docker_guard() -> None:
    if (os.environ.get("DOCKER_HOST") != "unix:///run/user/1001/docker.sock"
            or os.environ.get("XDG_RUNTIME_DIR") != "/run/user/1001"):
        raise Refused("unqualified_docker_socket")
    root = command("docker", "info", "--format", "{{.DockerRootDir}}").strip()
    options = json.loads(command("docker", "info", "--format", "{{json .SecurityOptions}}"))
    if root != "/home/aiops/.local/share/docker" or "name=rootless" not in options:
        raise Refused("unqualified_rootless_engine")


def compose_args(source: Path, override: Path | None = None) -> list[str]:
    args = ["docker", "compose", "-p", PROJECT, "--project-directory", str(source),
            "--env-file", str(source / ".env"), "-f", str(source / "compose.yml")]
    if override is not None:
        args += ["-f", str(override)]
    return args


def inspect_owned(source: Path, *, require_healthy: bool) -> dict[str, str]:
    names = [PROJECT + "-" + suffix for suffix in SERVICES.values()]
    items = json.loads(command("docker", "inspect", *names))
    if len(items) != len(SERVICES):
        raise Refused("incomplete_service_inventory")
    images: dict[str, str] = {}
    for item in items:
        labels = (item.get("Config") or {}).get("Labels") or {}
        service = labels.get("com.docker.compose.service")
        if (service not in SERVICES
                or item.get("Name", "").lstrip("/") != PROJECT + "-" + SERVICES[service]
                or labels.get("com.docker.compose.project") != PROJECT
                or labels.get("com.docker.compose.project.working_dir") != str(source)
                or str(source / "compose.yml") not in labels.get("com.docker.compose.project.config_files", "").split(",")
                or not item.get("State", {}).get("Running")
                or (require_healthy and item.get("State", {}).get("Health", {}).get("Status") != "healthy")):
            raise Refused("nonowned_or_unhealthy_container")
        image = item.get("Image", "")
        if not re.fullmatch(r"sha256:[a-f0-9]{64}", image):
            raise Refused("missing_original_image_identity")
        images[service] = image
    if set(images) != set(SERVICES):
        raise Refused("service_identity_mismatch")
    return images


def preflight_host(source: Path) -> dict[str, str]:
    docker_guard()
    if not source.is_dir() or source.is_symlink() or not (source / "compose.yml").is_file():
        raise Refused("missing_live_compose")
    env = source / ".env"
    if not env.is_file() or env.is_symlink() or (env.stat().st_mode & 0o077):
        raise Refused("missing_or_exposed_live_env")
    cfg = json.loads(command(*compose_args(source), "config", "--format", "json"))
    if cfg.get("name") != PROJECT:
        raise Refused("compose_project_mismatch")
    for service, suffix in SERVICES.items():
        entry = cfg.get("services", {}).get(service, {})
        if entry.get("container_name") != PROJECT + "-" + suffix:
            raise Refused("compose_service_name_mismatch")
    portal_env = cfg["services"]["aiops2-portal"].get("environment") or {}
    token = portal_env.get("AIOPS_PORTAL_READ_TOKEN", "")
    internal = portal_env.get("AIOPS_INTERNAL_TOKEN", "")
    if (not isinstance(token, str) or not 32 <= len(token) <= 256
            or not token.isascii() or any(c.isspace() for c in token)
            or token == internal):
        raise Refused("portal_viewer_auth_not_configured")
    return inspect_owned(source, require_healthy=True)


def write_override(path: Path, tags: dict[str, str]) -> None:
    # Only hard-coded service keys and locally generated Docker image tags.
    if set(tags) != set(SERVICES) or not all(re.fullmatch(r"[a-z0-9:._-]+", t) for t in tags.values()):
        raise Refused("invalid_image_override")
    body = "services:\n" + "".join(
        f"  {service}:\n    image: {tags[service]}\n" for service in SERVICES
    )
    with path.open("x", encoding="utf-8") as f:
        f.write(body)
    path.chmod(0o600)


def wait_healthy(source: Path) -> None:
    for _ in range(24):
        try:
            inspect_owned(source, require_healthy=True)
            return
        except Refused:
            time.sleep(5)
    raise Refused("targeted_services_unhealthy")


def verify_release_state(state: Path, stable_sha: str) -> None:
    """Read-only gate shared by host inspection and explicitly approved apply."""
    if (not state.is_dir() or state.is_symlink()
            or not (state / "applied.sha").is_file()
            or (state / "applied.sha").is_symlink()):
        raise Refused("missing_existing_operator_release_state")
    if (state / "DEPLOYMENT_BLOCKED").exists():
        raise Refused("existing_deployment_block_marker")
    if (not SHA.fullmatch(stable_sha)
            or (state / "applied.sha").stat().st_size != 41
            or (state / "applied.sha").read_text(encoding="ascii") != stable_sha + "\n"):
        raise Refused("applied_sha_not_matching_approved_stable")


def apply(delivery: Path, source: Path, state: Path, sha: str, stable_sha: str) -> dict:
    verify_release_state(state, stable_sha)
    # Never alter local source files, non-owned containers or persistent volumes.
    originals = preflight_host(source)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    receipt_dir = Path(tempfile.mkdtemp(prefix="p0-rollback-" + stamp + "-", dir=state))
    receipt_dir.chmod(0o700)
    old_tags = {}
    new_tags = {}
    for service, suffix in SERVICES.items():
        old_tags[service] = "aiops2-p0-old-" + suffix + ":" + sha[:12]
        new_tags[service] = "aiops2-p0-new-" + suffix + ":" + sha[:12]
        command("docker", "tag", originals[service], old_tags[service])
    rollback_file, candidate_file = receipt_dir / "rollback.yml", receipt_dir / "candidate.yml"
    write_override(rollback_file, old_tags)
    write_override(candidate_file, new_tags)
    switched = False
    try:
        for service, suffix in SERVICES.items():
            command("docker", "build", "-f", str(delivery / "app" / suffix / "Dockerfile"),
                    "-t", new_tags[service], str(delivery / "app"))
        # --no-deps is mandatory: never recreate database, Temporal, Copilot,
        # other containers, networks or volumes. No broad compose up/down.
        switched = True
        command(*compose_args(source, candidate_file), "up", "-d", "--no-deps",
                "--no-build", "--force-recreate", *SERVICES)
        wait_healthy(source)
        observed = inspect_owned(source, require_healthy=True)
        expected = {service: json.loads(command("docker", "image", "inspect", "--format",
                                                  "{{json .Id}}", new_tags[service]))
                    for service in SERVICES}
        if observed != expected:
            raise Refused("candidate_image_identity_mismatch")
        # Read-only local portal smoke. Full E2E remains NOT_TESTED.
        command("docker", "exec", PROJECT + "-portal", "python", "-c",
                "import urllib.request; b=urllib.request.urlopen("
                "'http://127.0.0.1:777/demo-studio',timeout=5).read(131073); "
                "assert b'ACME Demo Studio' in b and len(b)<=131072")
    except BaseException:
        if switched:
            try:
                command(*compose_args(source, rollback_file), "up", "-d", "--no-deps",
                        "--no-build", "--force-recreate", *SERVICES)
                wait_healthy(source)
                if inspect_owned(source, require_healthy=True) != originals:
                    raise Refused("rollback_image_identity_mismatch")
            except BaseException:
                (state / "DEPLOYMENT_BLOCKED").write_text(
                    "P0 rollback incomplete; operator intervention required\n")
                raise Refused("rollback_incomplete_operator_intervention") from None
        raise Refused("deployment_failed_original_images_preserved") from None
    return {"assessment": "APPLIED_UNATTESTED", "overall": "NO_GO",
            "candidate_sha": sha, "rollback_manifest": str(rollback_file),
            "read_only_portal_smoke": "PASS_LOCAL_ONLY",
            "e2e": "NOT_TESTED", "applied_sha": "NOT_WRITTEN",
            "rollback_exercised": "NOT_TESTED"}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--delivery", type=Path, default=Path(__file__).resolve().parents[1])
    p.add_argument("--stable-sha", required=True)
    p.add_argument("--candidate-sha", required=True)
    p.add_argument("--source-dir", type=Path)
    p.add_argument("--state-dir", type=Path, default=Path("/home/aiops/aiops2-auto-deploy"))
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true")
    mode.add_argument("--inspect-host", action="store_true",
                      help="read-only Docker/Compose ownership and release-state qualification")
    p.add_argument("--operator-approved", action="store_true")
    a = p.parse_args(argv)
    try:
        delivery = a.delivery.resolve(strict=True)
        result = plan(delivery, a.stable_sha, a.candidate_sha)
        if result["assessment"] == "BLOCKED":
            raise Refused("unsupported_candidate_paths")
        if a.inspect_host:
            if a.source_dir is None or a.source_dir.is_symlink() or a.state_dir.is_symlink():
                raise Refused("explicit_nonsymlinked_source_and_state_required")
            state = a.state_dir.resolve(strict=True)
            source = a.source_dir.resolve(strict=True)
            verify_release_state(state, a.stable_sha)
            # docker info, compose config and inspect only: no build, up or writes.
            owned = preflight_host(source)
            result = {
                "schema": SCHEMA, "assessment": "HOST_PREFLIGHT_PASS_UNATTESTED",
                "overall": "NO_GO", "candidate_sha": a.candidate_sha,
                "stable_sha": a.stable_sha, "owned_services": sorted(owned),
                "release_state": "MATCH_UNATTESTED",
                "docker_compose_ownership": "PASS_LOCAL_ONLY",
                "poller_migration": "NOT_TESTED", "rollback": "NOT_TESTED",
                "applied_sha": "NOT_ATTESTED", "e2e": "NOT_TESTED",
            }
        elif a.apply:
            if (not a.operator_approved or os.environ.get("AIOPS_RELEASE_APPLY") != "YES"
                    or a.source_dir is None):
                raise Refused("explicit_operator_approval_required")
            if a.source_dir.is_symlink() or a.state_dir.is_symlink():
                raise Refused("symlinked_operator_directory")
            result = apply(delivery, a.source_dir.resolve(strict=True),
                           a.state_dir.resolve(strict=True), a.candidate_sha, a.stable_sha)
        print(json.dumps(result, sort_keys=True))
        return 0 if result["assessment"] != "BLOCKED" else 2
    except (Refused, OSError, ValueError, subprocess.TimeoutExpired):
        print(json.dumps({"schema": SCHEMA, "assessment": "BLOCKED", "overall": "NO_GO",
                          "reason": "preflight_or_transaction_refused",
                          "e2e": "NOT_TESTED", "applied_sha": "NOT_ATTESTED"}))
        return 2


if __name__ == "__main__":
    sys.exit(main())
