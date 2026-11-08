#!/usr/bin/env python3
"""AIOps2 live Debian correlation gate: one-shot, read-only, no deployment.

Run on the Debian host with Docker access. Queries live Core and PostgreSQL
through existing containers, without exporting credentials or modifying data.
Exit 0 only when the configured coverage gate passes; otherwise exit 2.
"""
import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

CORE = "aiops2-rebuild-core"
DB = "aiops2-rebuild-postgres"
SQL = r"""
BEGIN TRANSACTION READ ONLY;
SELECT json_build_object(
  'incidents_total', (SELECT count(*) FROM aiops.incidents),
  'runs_total', (SELECT count(*) FROM aiops.runs),
  'glpi_links_total', (SELECT count(*) FROM aiops.glpi_ticket_links),
  'glpi_confirmed', (SELECT count(*) FROM aiops.glpi_ticket_links
                     WHERE state='CONFIRMED' AND glpi_ticket_id IS NOT NULL),
  'glpi_other_states', (SELECT coalesce(json_object_agg(state, n), '{}'::json)
    FROM (SELECT state, count(*) n FROM aiops.glpi_ticket_links GROUP BY state) x),
  'campaigns', (SELECT coalesce(json_agg(row_to_json(x)), '[]'::json) FROM (
    SELECT CASE WHEN i.incident_id LIKE 'INC-FS1130-%' THEN 'FS1130'
                WHEN i.incident_id LIKE 'INC-FS1250-%' THEN 'FS1250'
                ELSE 'AUTRES' END campaign,
           count(*) incidents,
           count(g.glpi_ticket_id) ticket_links,
           count(*) FILTER (WHERE g.incident_id IS NULL) missing_links
    FROM aiops.incidents i
    LEFT JOIN aiops.glpi_ticket_links g ON g.incident_id=i.incident_id
    GROUP BY 1 ORDER BY 1
  ) x),
  'unlinked_sample', (SELECT coalesce(json_agg(row_to_json(x)), '[]'::json) FROM (
    SELECT i.incident_id, i.source, i.synthetic
    FROM aiops.incidents i
    LEFT JOIN aiops.glpi_ticket_links g ON g.incident_id=i.incident_id
    WHERE g.incident_id IS NULL
    ORDER BY i.incident_id LIMIT 20
  ) x),
  'critic_denials', (SELECT coalesce(json_object_agg(status, n), '{}'::json)
    FROM (SELECT status, count(*) n FROM aiops.critic_denial_outbox GROUP BY status) x),
  'fs1250', (SELECT coalesce(json_agg(row_to_json(x)), '[]'::json) FROM (
    SELECT r.run_id, r.incident_id, r.status AS run_status,
           c.status AS denial_status, c.policy_decision_id,
           g.glpi_ticket_id, g.state AS glpi_state
    FROM aiops.runs r
    LEFT JOIN aiops.critic_denial_outbox c ON c.run_id=r.run_id
    LEFT JOIN aiops.glpi_ticket_links g ON g.incident_id=r.incident_id
    WHERE r.incident_id LIKE 'INC-FS1250-%'
    ORDER BY r.run_id LIMIT 20
  ) x)
)::text;
COMMIT;
"""

def invoke(args, input_text=None, timeout=30):
    p = subprocess.run(args, input=input_text, text=True,
                       capture_output=True, timeout=timeout, check=False)
    if p.returncode:
        raise RuntimeError(f"{args[0]} command failed (exit {p.returncode})")
    return p.stdout

def database_snapshot():
    # Credentials remain inside PostgreSQL container. No passwords on argv/stdout.
    shell = 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -X -A -t -v ON_ERROR_STOP=1'
    output = invoke(["docker", "exec", "-i", DB, "sh", "-c", shell], SQL)
    objects = [line for line in output.splitlines() if line.startswith("{")]
    if len(objects) != 1:
        raise ValueError("unexpected PostgreSQL result format")
    return json.loads(objects[0])

def api_snapshot():
    script = """
import json, urllib.request, urllib.error
targets = {
 'core': 'http://127.0.0.1:810/health',
 'twin': 'http://aiops2-rebuild-twin:811/health',
 'worker': 'http://aiops2-rebuild-worker:815/health',
 'policy': 'http://aiops2-rebuild-policy:813/health',
 'evidence': 'http://aiops2-rebuild-evidence:812/health',
 'intelligence': 'http://aiops2-rebuild-intelligence:817/health',
 'glpi': 'http://aiops2-rebuild-glpi:80/',
}
out={}
for name,url in targets.items():
 try:
  req=urllib.request.Request(url,headers={'User-Agent':'aiops2-correlation-gate/1'})
  with urllib.request.urlopen(req,timeout=4) as r: out[name]=r.status
 except urllib.error.HTTPError as e: out[name]=e.code
 except Exception as e: out[name]=type(e).__name__
print(json.dumps(out))
"""
    return json.loads(invoke(["docker", "exec", "-i", CORE, "python3", "-"], script))

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--require-all-glpi", action="store_true",
                        help="Strict gate: every incident must have a confirmed GLPI ticket")
    args = parser.parse_args()
    report = {"schema": "aiops2-live-correlation-gate-v1",
              "timestamp_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
              "read_only": True}
    try:
        report["database"] = database_snapshot()
        report["api_health"] = api_snapshot()
        failures = [f"{name}:HTTP_{code}" for name,code in report["api_health"].items()
                    if code != 200]
        db = report["database"]
        if args.require_all_glpi and db["glpi_confirmed"] != db["incidents_total"]:
            failures.append("GLPI_COVERAGE_INCOMPLETE")
        report["gate"] = "PASS" if not failures else "HOLD"
        report["failures"] = failures
    except (OSError, RuntimeError, ValueError, subprocess.TimeoutExpired) as exc:
        report["gate"] = "HOLD"
        report["failures"] = [type(exc).__name__ + ": " + str(exc)[:120]]
    output = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output + "\n", encoding="utf-8")
        print(f"Report: {args.output}")
    db = report.get("database", {})
    print(f"GATE={report['gate']} incidents={db.get('incidents_total', '?')} "
          f"glpi_confirmed={db.get('glpi_confirmed', '?')} "
          f"failures={','.join(report['failures']) or 'none'}")
    for campaign in db.get("campaigns", []):
        print(f"  {campaign['campaign']}: incidents={campaign['incidents']} "
              f"links={campaign['ticket_links']} missing={campaign['missing_links']}")
    return 0 if report["gate"] == "PASS" else 2

if __name__ == "__main__":
    sys.exit(main())
