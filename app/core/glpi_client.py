"""GLPI REST client for real tickets, including explicitly labelled DEMO tickets.

Secrets are only read from environment. Never include credentials in errors/logs.
"""
import os
import requests

class GlpiError(RuntimeError): pass

class Glpi:
    def __init__(self):
        self.base=os.getenv("AIOPS_GLPI_URL","").rstrip("/")
        self.app_token=os.getenv("AIOPS_GLPI_APP_TOKEN","")
        self.user_token=os.getenv("AIOPS_GLPI_USER_TOKEN","")
        self.timeout=int(os.getenv("AIOPS_GLPI_TIMEOUT_SECONDS","15"))
        if not self.base.startswith(("http://","https://")) or not self.app_token or not self.user_token:
            raise GlpiError("GLPI_API_NOT_CONFIGURED")
        self.session=None
    def _request(self,method,path,**kwargs):
        headers={"App-Token":self.app_token}
        if self.session:headers["Session-Token"]=self.session
        else:headers["Authorization"]="user_token "+self.user_token
        try:
            response=requests.request(method,self.base+"/apirest.php/"+path,
                                      headers=headers,timeout=self.timeout,**kwargs)
            response.raise_for_status()
            return response.json()
        except (requests.RequestException,ValueError) as exc:
            raise GlpiError("GLPI_API_"+type(exc).__name__) from None
    def __enter__(self):
        data=self._request("GET","initSession")
        self.session=data.get("session_token")
        if not self.session:raise GlpiError("GLPI_SESSION_MISSING")
        return self
    def __exit__(self,*args):
        if self.session:
            try:self._request("GET","killSession")
            except GlpiError:pass
    def create(self,incident):
        synthetic=bool(incident["synthetic"])
        marker="[DEMO] " if synthetic else ""
        name=(marker+incident["title"])[:250]
        # Correlation marker is human-visible and also used by the durable outbox.
        content=("AIOps2 incident: "+incident["incident_id"]+"\n"
                 +"External ID: "+incident["external_id"]+"\n"
                 +"Mode: "+("DEMO — SYNTHETIC / NO LIVE REMEDIATION" if synthetic else "LIVE")+"\n"
                 +"Source: "+str(incident["source"])[:100])
        priority={"P1":5,"P2":4,"P3":3,"P4":2}.get(incident["severity"],3)
        data=self._request("POST","Ticket",json={"input":{
            "name":name,"content":content,"type":1,"status":1,
            "priority":priority,"urgency":priority,"impact":priority}})
        ticket_id=data.get("id")
        if type(ticket_id) is not int or ticket_id<=0:
            raise GlpiError("GLPI_TICKET_ID_MISSING")
        return ticket_id
