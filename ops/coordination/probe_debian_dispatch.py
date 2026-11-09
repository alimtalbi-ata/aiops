#!/usr/bin/env python3
"""Read-only discovery of an existing Debian GitHub/Codex dispatch chain.

No network calls, no subprocess execution, no cron edits. Input is captured
text from authorized operator inspection. Emits evidence gaps, not success.
"""
import argparse
import json
import re
from pathlib import Path

HINTS = {
    "poller": re.compile(r"(?i)(poll\.sh|github.*poll|poll.*github)"),
    "publisher": re.compile(r"(?i)(publish.*(github|report)|report.*publish)"),
    "codex": re.compile(r"(?i)(codex\s+(exec|resume)|codex-cli|codex\.cloud)"),
    "queue": re.compile(r"(?i)(task_request|dispatch|inbox|work[_-]?queue)"),
    "receipt": re.compile(r"(?i)(task_accepted|session[_-]?id|receipt|latest\.json)"),
}
SECRET = re.compile(r"(?i)(gh[pousr]_[a-z0-9_]+|github_pat_[a-z0-9_]+|(?:token|password|secret|authorization)\s*[:=]\s*\S+)")
MAX_INPUT = 262144

def evaluate(sources):
    signals = {key: [] for key in HINTS}
    for label, content in sources.items():
        if len(content.encode("utf-8")) > MAX_INPUT:
            raise ValueError("input exceeds read-only inspection limit")
        for line_no, line in enumerate(content.splitlines(), 1):
            if SECRET.search(line):
                continue
            for key, regex in HINTS.items():
                if regex.search(line):
                    signals[key].append({"source": label, "line": line_no})
    # Matching a name is never proof of a live dispatcher.
    return {
        "schema_version": "aiops.dispatch-discovery.v1",
        "status": "DISPATCH_NOT_VERIFIED",
        "signals": signals,
        "required_proofs": [
            "existing cron/systemd job definition and enabled state",
            "actual inbound task transport and allowlist",
            "Codex execution invocation with session identifier",
            "TASK_ACCEPTED receipt correlated with a GitHub work item",
            "TASK_DONE receipt and Debian publisher round trip"
        ],
        "safety": "read-only pattern inspection; no dispatch performed"
    }

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshots", nargs="+", type=Path, help="sanitized cron/poller/runner snapshots")
    parser.add_argument("--output", type=Path, help="local output path")
    args = parser.parse_args(argv)
    sources = {}
    for p in args.snapshots:
        if p.is_symlink() or not p.is_file() or p.stat().st_size > MAX_INPUT:
            parser.error("snapshot must be bounded regular file")
        sources[p.name] = p.read_text(encoding="utf-8")
    report = evaluate(sources)
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 2  # Not a verified dispatch: fail closed even if patterns were found.

if __name__ == "__main__":
    raise SystemExit(main())
