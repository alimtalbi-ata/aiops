from pathlib import Path
import re
p=Path(__file__).resolve().parents[1]/'01-Architecture/PLATFORM-CONTRACT.yaml'; s=p.read_text()
for n,v in {'portal':7777,'glpi':8080,'n8n':5678,'prometheus':9090,'grafana':3000,'core':810,'twin':811,'evidence':812,'policy':813,'copilot':814,'simulator':816,'integration':817,'intelligence':818,'rag':819,'temporal':7233,'postgres':5432,'mariadb':3306}.items(): assert re.search(rf'\b{n}: {v}\b',s),n
for x in ['correlation_id','incident_id','run_id','event_id','evidence_id','decision_id','remediation_id','receipt_id']: assert x in s,x
for x in ['immutable_run_events: true','evidence_provenance_required: true','observed_at_and_known_at: true','demo_isolation_by_run_id: true','unknown_evidence_fails_closed: true','outbox_idempotent: true','temporal_single_executor: true','external_writes_policy_gated: true','legacy_retirement_requires_runtime_qualification: true']: assert x in s,x
print('CONTRACT=PASS'); print('PORTS=PASS'); print('IDENTITIES=PASS'); print('INVARIANTS=PASS')
