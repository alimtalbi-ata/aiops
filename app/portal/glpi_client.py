"""Small authenticated GLPI REST client for the Portal.

Only server-side credentials are used. Tokens and session IDs are never returned.
"""
import os
import requests


class GLPIError(RuntimeError):
    pass


class GLPIClient:
    def __init__(self):
        self.base=os.getenv("GLPI_API_URL","http://aiops2-glpi/apirest.php").rstrip("/")
        self.app_token=os.getenv("GLPI_APP_TOKEN","").strip()
        self.user_token=os.getenv("GLPI_USER_TOKEN","").strip()

    @property
    def configured(self):
        return bool(self.base and self.app_token and self.user_token)

    def _headers(self):
        return {"App-Token":self.app_token,"Content-Type":"application/json"}

    def _session(self):
        if not self.configured:
            raise GLPIError("glpi_credentials_not_configured")
        response=requests.get(
            self.base+"/initSession",
            headers={**self._headers(),"Authorization":"user_token "+self.user_token},
            timeout=10,
        )
        response.raise_for_status()
        token=(response.json() or {}).get("session_token")
        if not token:
            raise GLPIError("glpi_session_token_missing")
        return token

    def _call(self,method,path,**kwargs):
        token=self._session()
        try:
            response=requests.request(
                method,self.base+"/"+path.lstrip("/"),
                headers={**self._headers(),"Session-Token":token},
                timeout=15,**kwargs
            )
            response.raise_for_status()
            if not response.content:
                return {}
            return response.json()
        finally:
            try:
                requests.get(self.base+"/killSession",
                    headers={**self._headers(),"Session-Token":token},timeout=5)
            except requests.RequestException:
                pass

    def health(self):
        if not self.configured:
            return {"status":"UNCONFIGURED","configured":False,
                    "reason":"GLPI_APP_TOKEN and GLPI_USER_TOKEN are required"}
        token=None
        try:
            token=self._session()
            return {"status":"CONNECTED","configured":True,"authenticated":True}
        except requests.RequestException as exc:
            code=exc.response.status_code if exc.response is not None else None
            return {"status":"UNAVAILABLE" if code is None or code>=500 else "UNAUTHORIZED",
                    "configured":True,"authenticated":False,"http_status":code}
        except GLPIError as exc:
            return {"status":"UNAVAILABLE","configured":True,
                    "authenticated":False,"reason":str(exc)}
        finally:
            if token:
                try:
                    requests.get(self.base+"/killSession",
                        headers={**self._headers(),"Session-Token":token},timeout=5)
                except requests.RequestException:
                    pass

    def get_ticket(self,ticket_id):
        if not str(ticket_id).isdigit():
            raise ValueError("invalid_glpi_ticket_id")
        return self._call("GET","Ticket/"+str(ticket_id),params={"expand_dropdowns":"true"})

    def search_tickets(self,query,limit=25):
        query=str(query).strip()
        if len(query)<2:
            raise ValueError("query_must_have_at_least_2_characters")
        params={
            "criteria[0][field]":"1",
            "criteria[0][searchtype]":"contains",
            "criteria[0][value]":query,
            "forcedisplay[0]":"2",
            "forcedisplay[1]":"1",
            "forcedisplay[2]":"12",
            "range":f"0-{max(1,min(int(limit),100))-1}",
        }
        return self._call("GET","search/Ticket",params=params)

    def list_ticket_followups(self,ticket_id,limit=100):
        if not str(ticket_id).isdigit():
            raise ValueError("invalid_glpi_ticket_id")
        count=max(1,min(int(limit),100))
        result=self._call("GET",f"Ticket/{int(ticket_id)}/ITILFollowup",
                          params={"range":f"0-{count-1}","order":"DESC"})
        if not isinstance(result,list):
            raise GLPIError("glpi_followup_list_invalid")
        return result

    def add_private_followup(self,ticket_id,marker,content):
        """Idempotently add an internal note; never create a public follow-up."""
        if not str(ticket_id).isdigit():
            raise ValueError("invalid_glpi_ticket_id")
        if not isinstance(marker,str) or not marker.startswith("[AIOPS2-HITL-PROPOSAL:"):
            raise ValueError("invalid_aiops_followup_marker")
        if not isinstance(content,str) or marker not in content or len(content)>6000:
            raise ValueError("invalid_aiops_followup_content")
        existing=self.list_ticket_followups(ticket_id,100)
        for item in existing:
            if isinstance(item,dict) and marker in str(item.get("content","")):
                return {"id":item.get("id"),"idempotent":True,"is_private":item.get("is_private") in (1,True,"1")}
        result=self._call("POST","ITILFollowup",json={"input":{
            "itemtype":"Ticket","items_id":int(ticket_id),"content":content,"is_private":1
        }})
        if not isinstance(result,dict) or not result.get("id"):
            raise GLPIError("glpi_followup_receipt_invalid")
        return {"id":result["id"],"idempotent":False,"is_private":True}
