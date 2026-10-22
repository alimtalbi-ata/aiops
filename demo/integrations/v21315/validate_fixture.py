#!/usr/bin/env python3
"""Offline, read-only validation of ACME demo fixtures. No GLPI/Grafana/n8n writes."""
import json,sys
from pathlib import Path
p=Path(sys.argv[1]) if len(sys.argv)>1 else Path(__file__).with_name("acme-fixtures.json")
d=json.loads(p.read_text(encoding="utf-8"))
assert d["provenance"]=="SIMULATED_TARGET"
items=d["ci"]; names={i["id"] for i in items}
assert len(names)==len(items) and len(items)>=6
for item in items:
 assert set(item["depends_on"]) <= names
for incident in d["incidents"]:
 assert incident["ci"] in names
 assert incident["status"]=="simulated"
 assert incident["live_remediation"] is False
 assert not set(incident["allowed_actions"]) & {"execute","restart","remediate"}
print("AIOPS_DEMO_FIXTURES=PASS",len(items),"CIs",len(d["incidents"]),"incidents")
