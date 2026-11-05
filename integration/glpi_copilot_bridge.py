#!/usr/bin/env python3
"""GLPI native-followup Copilot bridge. No ticket status changes or remediation."""
import os, sys, json, re, html, time, urllib.request, urllib.error, datetime
from portal.glpi_client import GLPIClient

TAG = "AIOPS2-GLPI-COPILOT-V1"
CURSOR = "/tmp/aiops2-glpi-copilot-state.json"
URL = os.getenv("AIOPS_COPILOT_URL", "http://aiops2-copilot:814").rstrip("/")
LIMIT = int(os.getenv("AIOPS_COPILOT_TICKET_LIMIT", "100"))
TIMEOUT = 9

def log(*args):
    print(datetime.datetime.now(datetime.timezone.utc).isoformat(), *args, flush=True)

def rows(result):
    if isinstance(result, list): return result
    if isinstance(result, dict):
        for key in ("data", "items"):
            if isinstance(result.get(key), list): return result[key]
    raise RuntimeError("Unexpected GLPI response shape")

def plain(s):
    s = re.sub(r"<[^>]+>", " ", str(s or ""))
    return html.unescape(s).strip()

def followups(client, tid):
    return rows(client._call("GET", "Ticket/%s/ITILFollowup" % tid))

def post(client, tid, body, marker):
    result = client._call("POST", "ITILFollowup", json={"input":[{
        "itemtype": "Ticket", "items_id": int(tid), "is_private": 0,
        "content": '<div><strong>🤖 AIOps2 Copilot</strong><p>'+
          html.escape(body).replace("\n","<br>")+
          '</p><small>'+html.escape(marker)+'</small></div>'
    }]})
    log("POSTED", tid, result)

def ai_query(question, run_id=None):
    payload={"question":question[:1500], "run_id":run_id}
    req=urllib.request.Request(
        URL+"/api/copilot/query",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type":"application/json"},method="POST")
    try:
        with urllib.request.urlopen(req,timeout=TIMEOUT) as r:
            d=json.load(r)
        answer=str(d.get("answer","")).strip()
        if not answer: raise ValueError("empty answer")
        sources=d.get("sources",[])
        limitations=d.get("limitations",[])
        return ("Réponse du service Copilot (à vérifier avant action) :\n"+
            answer[:4500]+"\nSources déclarées : "+", ".join(map(str,sources))[:500]+
            "\nLimites : "+", ".join(map(str,limitations))[:700]+
            "\nAucune action de remédiation autorisée par cette réponse.")
    except Exception as exc:
        return ("Service IA non disponible ou réponse invalide ("+
            type(exc).__name__+"). Aucune réponse IA inventée. "+
            "Conserver le ticket ouvert et demander une investigation humaine.")

def process_ticket(client, ticket):
    tid=int(ticket["id"])
    if str(ticket.get("is_deleted",0))=="1": return
    follow=followups(client,tid)
    existing=[plain(x.get("content")) for x in follow]
    welcome_marker=TAG+":WELCOME:"+str(tid)
    if not any(welcome_marker in x for x in existing):
        post(client,tid,
            "Assistant Copilot disponible sur ce ticket. Pour poser une question, "+
            "ajoutez un suivi public commençant par @copilot, suivi de votre question. "+
            "Je réponds ici à partir du service Copilot connecté, avec ses sources. "+
            "Aucune approbation, suppression ou résolution automatique.",
            welcome_marker)
        follow=followups(client,tid)
    # Process each human followup only once, and never answer our own messages.
    all_text=[plain(x.get("content")) for x in follow]
    for f in sorted(follow,key=lambda x:int(x.get("id",0))):
        fid=int(f.get("id",0))
        body=plain(f.get("content"))
        if TAG in body: continue
        match=re.match(r"^@copilot\b\s*[:,-]?\s*(.*)$",body,re.I|re.S)
        if not match: continue
        response_marker=TAG+":ANSWER:"+str(fid)
        if any(response_marker in x for x in all_text): continue
        question=match.group(1).strip()
        if not question:
            answer="Veuillez écrire une question après @copilot."
        else:
            # Only pass run_id when explicitly present in the ticket text.
            content=plain(ticket.get("content"))
            m=re.search(r"\bRUN-[A-Z0-9]{12,24}\b",content)
            answer=ai_query(question, m.group(0) if m else None)
        post(client,tid,"Question (suivi %d) : %s\n\n%s"%(fid,question[:500],answer),
             response_marker)
        all_text.append(response_marker)

def main():
    client=GLPIClient()
    if not client.configured: raise RuntimeError("GLPI credentials missing")
    # GLPI REST range returns the newest visible tickets only if sorted by ID.
    # Use a bounded listing and sort locally; no mutation of ticket status.
    items=rows(client._call("GET","Ticket",params={
        "range":"0-%d"%(LIMIT-1),"sort":"id","order":"DESC"}))
    log("VISIBLE_TICKETS",len(items))
    count=0
    for item in sorted(items,key=lambda x:int(x.get("id",0)),reverse=True):
        tid=item.get("id")
        if not tid: continue
        try:
            ticket=client.get_ticket(str(tid))
            process_ticket(client,ticket)
            count+=1
        except Exception as exc:
            log("TICKET_ERROR",tid,type(exc).__name__,str(exc)[:200])
    log("FINISHED",count)

if __name__=="__main__": main()
