"""Read-only GLPI ticket KPI sourced from the durable Core correlation outbox."""
from fastapi import HTTPException
from shared.db import db

def register_glpi_kpi(app):
    @app.get("/api/kpi/glpi")
    def glpi_kpi():
        with db() as c:
            table=c.execute("select to_regclass('aiops.glpi_ticket_links')").fetchone()[0]
            counts=c.execute("""select count(*),count(*) filter(where synthetic),
                    count(*) filter(where external_id like 'FS1130-%')
                    from aiops.incidents""").fetchone()
            if not table:
                return {"source":"CORE_GLPI_OUTBOX","configured":False,
                        "incidents_total":counts[0],"incidents_synthetic":counts[1],
                        "fs1130_incidents":counts[2],
                        "tickets_confirmed":0,"tickets_unknown":0,
                        "tickets_pending":0,"tickets_claimed":0,
                        "tickets_error":0,"sync_rate_pct":None,
                        "latency_median_seconds":None,
                        "note":"No outbox exists; no ticket creation confirmed"}
            rows=c.execute("""select
                    count(*) filter(where l.state='CONFIRMED'),
                    count(*) filter(where l.state='UNKNOWN'),
                    count(*) filter(where l.state='PENDING'),
                    count(*) filter(where l.state='CLAIMED'),
                    count(*) filter(where l.state='ERROR'),
                    count(*) filter(where i.external_id like 'FS1130-%' and l.state='CONFIRMED'),
                    count(*) filter(where i.external_id like 'FS1130-%' and l.state='UNKNOWN'),
                    percentile_cont(0.5) within group
                      (order by extract(epoch from (l.confirmed_at-i.opened_at)))
                      filter(where l.state='CONFIRMED' and l.confirmed_at is not null)
                    from aiops.glpi_ticket_links l
                    join aiops.incidents i on i.incident_id=l.incident_id""").fetchone()
        return {"source":"CORE_GLPI_OUTBOX","configured":True,
                "incidents_total":counts[0],"incidents_synthetic":counts[1],
                "fs1130_incidents":counts[2],
                "tickets_confirmed":rows[0],"tickets_unknown":rows[1],
                "tickets_pending":rows[2],"tickets_claimed":rows[3],
                "tickets_error":rows[4],
                "fs1130_tickets_confirmed":rows[5],
                "fs1130_tickets_unknown":rows[6],
                "sync_rate_pct":round(100*rows[5]/counts[2],2) if counts[2] else None,
                "latency_median_seconds":round(rows[7],2) if rows[7] is not None else None,
                "note":"Confirmed means GLPI REST returned a ticket ID; UNKNOWN requires reconciliation"}
