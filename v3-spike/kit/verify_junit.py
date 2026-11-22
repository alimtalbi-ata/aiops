"""Fail-closed JUnit receipt verifier for V3 product preflight."""
import argparse
from pathlib import Path
import xml.etree.ElementTree as ET


def verify(directory: Path, expected: int) -> int:
    paths = sorted(directory.glob("*.xml"))
    if not paths:
        raise ValueError("missing JUnit XML")
    totals = {"tests": 0, "failures": 0, "errors": 0, "skipped": 0}
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
    return totals["tests"]


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("directory", type=Path)
    p.add_argument("--expected", type=int, required=True)
    args = p.parse_args()
    try:
        count = verify(args.directory, args.expected)
        print(f"PASS JUnit integrity {count}/{args.expected}")
    except (ValueError, OSError) as exc:
        p.exit(2, f"FAIL JUnit integrity: {exc}\n")
