#!/usr/bin/env python3
"""Read-only Docker resource ownership fence for an isolated deployment.

Stops installation before Docker Compose can adopt, replace or reuse resources
owned by another Compose project. Never prints Docker inspect payloads or secrets.
"""
from __future__ import annotations
import argparse
import json
import re
import subprocess
import sys


def docker(*args: str) -> tuple[int, str, str]:
    p=subprocess.run(["docker", *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                     text=True, check=False, timeout=15)
    # stderr is processed for error classification only and is NEVER displayed.
    return p.returncode, p.stdout, p.stderr

def is_missing(kind: str, stderr: str) -> bool:
    raw=stderr.lower()
    if kind=="container":
        return "no such object" in raw or "no such container" in raw
    if kind=="network":
        return "network" in raw and "not found" in raw or "no such network" in raw
    if kind=="volume":
        return "no such volume" in raw
    return False


def check_resource(kind: str, name: str, project: str) -> str | None:
    if kind=="container":
        code,value,error=docker("container","inspect",name)
    elif kind=="network":
        code,value=docker("network","inspect",name)
    elif kind=="volume":
        code,value=docker("volume","inspect",name)
    else:
        return "unknown_resource_kind"

    if code:
        if is_missing(kind,error):
            return None
        return f"{kind}_inspect_unavailable:{name}"
    try:
        parsed=json.loads(value)[0]
    except (ValueError,IndexError,TypeError):
        return f"{kind}_inspect_unparseable:{name}"
    labels=((parsed.get("Config") or {}).get("Labels") or {}) if kind=="container" else (parsed.get("Labels") or {})
    owner=labels.get("com.docker.compose.project")
    if owner != project:
        return f"{kind}_owned_by_other_project:{name}"
    return None


def inspect_resources(data: dict) -> list[tuple[str,str]]:
    result=[]
    for service in data.get("services",{}).values():
        if isinstance(service,dict) and service.get("container_name"):
            result.append(("container",service["container_name"]))
    for kind in ("networks","volumes"):
        for resource in data.get(kind,{}).values():
            if isinstance(resource,dict) and resource.get("name"):
                result.append(("network" if kind=="networks" else "volume",resource["name"]))
    return result


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project",required=True)
    args=parser.parse_args()
    if not re.fullmatch(r"[a-z][a-z0-9-]{2,28}",args.project) or args.project=="aiops2":
        print("OWNERSHIP_FENCE=FAIL|invalid_project",file=sys.stderr)
        return 2
    try:
        data=json.load(sys.stdin)
        resources=inspect_resources(data)
        problems=[]
        for kind,name in resources:
            if not name.startswith(args.project+"-"):
                problems.append("unisolated_resource:"+kind)
                continue
            issue=check_resource(kind,name,args.project)
            if issue: problems.append(issue)
    except (ValueError,TypeError,subprocess.TimeoutExpired,OSError) as error:
        print("OWNERSHIP_FENCE=FAIL|inspection_unavailable:"+type(error).__name__,file=sys.stderr)
        return 2
    if problems:
        for issue in problems:
            print("OWNERSHIP_FENCE=FAIL|"+issue,file=sys.stderr)
        return 1
    print("OWNERSHIP_FENCE=PASS|project="+args.project+"|resources_checked="+str(len(resources)))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
