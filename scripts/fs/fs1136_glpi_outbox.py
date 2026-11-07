#!/usr/bin/env python3
"""FS1136 GLPI ticket outbox: one ticket per Core incident, DEMO included.

Execute in Core container. --inspect is strictly read-only. --sync creates an
outbox and real GLPI tickets, requiring GLPI REST credentials configured.
A request with ambiguous outcome is never blindly retried (UNKNOWN).
"""
import argparse
import json
import os
import sys
from datetime import datetime
from shared.db import db
from core.glpi_client import Glpi,GlpiError

DDL="""create table if not exists aiops.glpi_ticket_links(
 incident_id text primary key references aiops.incidents(incident_id),
 glpi_ticket_id bigint unique,
 state text not null check(state in ('PENDING','CLAIMED','CONFIRMED','UNKNOWN','ERROR')),
 attempts integer not null default 0,
 last_error text,
 claimed_at timestamptz,
 confirmed_at timestamptz,
 created_at timestamptz not null default now()
)"""
def emit(**data):print(json.dumps(data,ensure_ascii=False,default=str),flush=True)
def inspect():
    with db() as c:
        n=c.execute("""select count(*),count(*) filter(where synthetic)
             from aiops.incidents where external_id like 'FS1130-%'""").fetchone()
        table=c.execute("select to_regclass('aiops.glpi_ticket_links')").fetchone()[0]
        if table:
            states=c.execute("""select state,count(*) from aiops.glpi_ticket_links
                where incident_id in (select incident_id from aiops.incidents
                                      where external_id like 'FS1130-%')
                group by state""").fetchall()
        else:states=[]
    emit(type="inspect",fs1130_incidents=n[0],fs1130_synthetic=n[1],
         outbox_exists=bool(table),ticket_states=dict(states),mutation="NONE")
def sync(limit):
    # Fail before ANY DB mutation when GLPI REST is unconfigured.
    client=Glpi()
    with client:
        with db() as c:
            c.execute(DDL)
            c.execute("""insert into aiops.glpi_ticket_links(incident_id,state)
                         select incident_id,'PENDING' from aiops.incidents
                         where external_id like 'FS1130-%'
                         on conflict(incident_id) do nothing""")
        created=0
        for _ in range(limit):
            with db() as c:
                # CLAIMED is committed BEFORE remote POST: a crash cannot silently duplicate tickets.
                row=c.execute("""select l.incident_id,i.external_id,i.title,i.severity,
                                        i.source,i.synthetic
                    from aiops.glpi_ticket_links l
                    join aiops.incidents i on i.incident_id=l.incident_id
                    where l.state='PENDING' and i.external_id like 'FS1130-%'
                    order by l.created_at,l.incident_id
                    for update of l skip locked limit 1""").fetchone()
                if not row:break
                c.execute("""update aiops.glpi_ticket_links set state='CLAIMED',
                             claimed_at=now(),attempts=attempts+1
                             where incident_id=%s""",(row[0],))
            incident=dict(zip(("incident_id","external_id","title","severity","source","synthetic"),row))
            try:
                ticket=client.create(incident)
            except GlpiError as exc:
                # Ambiguous remote outcome: do not retry without GLPI reconciliation.
                with db() as c:
                    c.execute("""update aiops.glpi_ticket_links set state='UNKNOWN',
                        last_error=%s where incident_id=%s""",(str(exc)[:120],row[0]))
                emit(type="ticket",incident_id=row[0],state="UNKNOWN",error=str(exc))
                continue
            with db() as c:
                c.execute("""update aiops.glpi_ticket_links set state='CONFIRMED',
                             glpi_ticket_id=%s,confirmed_at=now(),last_error=null
                             where incident_id=%s and state='CLAIMED'""",(ticket,row[0]))
            emit(type="ticket",incident_id=row[0],state="CONFIRMED",glpi_ticket_id=ticket)
            created+=1
    emit(type="summary",created=created,limit=limit,scope="FS1130_ONLY",
         warning="UNKNOWN rows require reconciliation; no automatic duplicate retries")
    inspect()
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--inspect",action="store_true")
    p.add_argument("--sync",action="store_true")
    p.add_argument("--limit",type=int,default=50)
    args=p.parse_args()
    if args.inspect==args.sync:p.error("choose exactly one of --inspect or --sync")
    if args.limit<1 or args.limit>100:p.error("limit must be 1..100")
    if args.inspect:inspect()
    else:sync(args.limit)
if __name__=="__main__":
    try:main()
    except Exception as exc:
        emit(type="fatal",error_type=type(exc).__name__,
             reason=str(exc)[:160] if isinstance(exc,GlpiError) else "INTEGRATION_FAILURE")
        sys.exit(2)
