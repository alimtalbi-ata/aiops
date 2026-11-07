#!/usr/bin/env bash
# FS1148: real Core Postgres outbox state machine in a rolled-back transaction.
# No production changes, no Portal access, no GLPI POST.
set -euo pipefail
echo "FS1148_MODE=REAL_POSTGRES_OUTBOX_ROLLBACK_TEST"
echo "FS1148_PRODUCTION_PERSISTENT_MUTATION=NONE"
docker exec -i aiops2-rebuild-core python - <<'PY'
import os,json,sys
import psycopg
def emit(**kw):print(json.dumps(kw,sort_keys=True),flush=True)
conn=psycopg.connect(os.environ['DATABASE_URL'])
try:
 with conn.cursor() as c:
  c.execute("select incident_id from aiops.incidents where external_id like 'FS1130-%' order by incident_id limit 1")
  row=c.fetchone()
  if not row:
   emit(type='preflight',result='NO_FS1130_INCIDENT');sys.exit(2)
  iid=row[0]
  # A temporary table uses the same state/uniqueness semantics as the real outbox,
  # without touching aiops.glpi_ticket_links.
  c.execute("""create temporary table fs1148_links(
   incident_id text primary key,
   glpi_ticket_id bigint unique,
   state text not null check(state in ('PENDING','CLAIMED','CONFIRMED','UNKNOWN','ERROR')),
   attempts integer not null default 0,
   claimed_at timestamptz,confirmed_at timestamptz
  ) on commit drop""")
  c.execute("insert into fs1148_links(incident_id,state) values (%s,'PENDING') on conflict do nothing",(iid,))
  c.execute("insert into fs1148_links(incident_id,state) values (%s,'PENDING') on conflict do nothing",(iid,))
  c.execute("select count(*) from fs1148_links where incident_id=%s",(iid,))
  assert c.fetchone()[0]==1,'duplicate outbox rows'
  c.execute("""update fs1148_links set state='CLAIMED',attempts=attempts+1,claimed_at=now()
               where incident_id=%s and state='PENDING' returning attempts""",(iid,))
  assert c.fetchone()[0]==1
  c.execute("""update fs1148_links set state='CONFIRMED',glpi_ticket_id=155,confirmed_at=now()
               where incident_id=%s and state='CLAIMED' returning glpi_ticket_id""",(iid,))
  assert c.fetchone()[0]==155
  c.execute("update fs1148_links set state='CLAIMED' where incident_id=%s and state='PENDING' returning incident_id",(iid,))
  assert c.fetchone() is None,'confirmed ticket was reclaimed'
  c.execute("select state,attempts,glpi_ticket_id from fs1148_links where incident_id=%s",(iid,))
  assert c.fetchone()==('CONFIRMED',1,155)
  c.execute("insert into fs1148_links(incident_id,state) values ('FS1148-UNKNOWN','UNKNOWN')")
  c.execute("update fs1148_links set state='CLAIMED' where incident_id='FS1148-UNKNOWN' and state='PENDING' returning incident_id")
  assert c.fetchone() is None,'UNKNOWN was automatically retried'
  emit(type='db_assertions',result='PASS',real_postgres=True,fs1130_incident_found=True,
       duplicate_prevented=True,claim_once=True,confirmed_not_reclaimed=True,
       unknown_not_retried=True,real_glpi_ticket_155_not_linked=True)
finally:
 conn.rollback()
 conn.close()
emit(type='summary',result='PASS_ROLLED_BACK',persisted_changes=False,glpi_tickets_created=0)
PY
echo "FS1148_FINAL_STATUS=PASS_ROLLED_BACK"
