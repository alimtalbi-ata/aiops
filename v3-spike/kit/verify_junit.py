"""Fail-closed JUnit receipt verifier for V3 product preflight."""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET


def source_identities(source: Path):
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    names = {(node.name, method.name) for node in tree.body if isinstance(node, ast.ClassDef)
             for method in node.body if isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef))
             and method.name.startswith("test_")}
    if not names:
        raise ValueError("source has no test methods")
    return names


def verify(directory: Path, expected: int, source=None, sha=None, job=None, manifest=None) -> int:
    paths = sorted(directory.glob("*.xml"))
    if not paths:
        raise ValueError("missing JUnit XML")
    totals = {"tests": 0, "failures": 0, "errors": 0, "skipped": 0}
    identities = []
    for path in paths:
        if not path.is_file() or path.stat().st_size == 0:
            raise ValueError("empty JUnit XML")
        try:
            root = ET.parse(path).getroot()
        except ET.ParseError as exc:
            raise ValueError("malformed JUnit XML") from exc
        suites = [root] if root.tag == "testsuite" else list(root) if root.tag == "testsuites" else []
        if not suites or any(s.tag != "testsuite" for s in suites):
            raise ValueError("invalid JUnit root")
        for suite in suites:
            cases = suite.findall("testcase")
            if not cases:
                raise ValueError("empty JUnit suite")
            for case in cases:
                classname, name = case.get("classname"), case.get("name")
                if source is not None and (not classname or not name):
                    raise ValueError("missing JUnit testcase identity")
                if classname and name:
                    identities.append((classname.rsplit(".", 1)[-1], name))
            for key in totals:
                raw = suite.get(key)
                if raw is None or not raw.isdecimal():
                    raise ValueError("missing/invalid JUnit counter: " + key)
                declared = int(raw)
                actual = len(cases) if key == "tests" else sum(
                    bool(case.findall(key[:-1] if key != "skipped" else "skipped"))
                    for case in cases
                )
                if declared != actual:
                    raise ValueError("JUnit counter mismatch: " + key)
                totals[key] += declared
    if totals["tests"] != expected or any(totals[k] for k in ("failures", "errors", "skipped")):
        raise ValueError("JUnit failed/incomplete: " + repr(totals))
    if source is not None:
        expected_ids = source_identities(Path(source))
        if (len(expected_ids) != expected or len(identities) != expected
                or len(set(identities)) != expected or set(identities) != expected_ids):
            raise ValueError("JUnit testcase identity mismatch/duplicate/substitution")
    if manifest is not None:
        if source is None or not sha or not job:
            raise ValueError("manifest requires source, SHA and job")
        import re
        if not re.fullmatch(r"[0-9a-f]{40}", sha):
            raise ValueError("invalid commit SHA")
        payload = {"sha": sha, "job": job, "source": str(source),
                   "source_sha256": hashlib.sha256(Path(source).read_bytes()).hexdigest(),
                   "tests": expected, "identities": sorted([list(x) for x in identities]),
                   "xml_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}}
        Path(manifest).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return totals["tests"]


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("directory", type=Path)
    p.add_argument("--expected", type=int, required=True)
    p.add_argument("--source", type=Path)
    p.add_argument("--sha")
    p.add_argument("--job")
    p.add_argument("--manifest", type=Path)
    args = p.parse_args()
    try:
        count = verify(args.directory, args.expected, args.source, args.sha, args.job, args.manifest)
        print(f"PASS JUnit integrity {count}/{args.expected}")
    except (ValueError, OSError, SyntaxError) as exc:
        p.exit(2, f"FAIL JUnit integrity: {exc}\n")
