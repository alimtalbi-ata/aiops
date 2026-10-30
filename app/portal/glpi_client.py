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
            "criteria[0][field]":"2",
            "criteria[0][searchtype]":"contains",
            "criteria[0][value]":query,
            "forcedisplay[0]":"2",
            "forcedisplay[1]":"1",
            "forcedisplay[2]":"12",
            "range":f"0-{max(1,min(int(limit),100))-1}",
        }
        return self._call("GET","search/Ticket",params=params)

    def create_ticket(self, name, content, *, priority=3):
        """Create one GLPI incident ticket and return its numeric identifier."""
        payload = {
            "input": {
                "name": str(name)[:250],
                "content": str(content),
                "type": 1,
                "status": 1,
                "priority": max(1, min(int(priority), 6)),
            }
        }
        result = self._call("POST", "Ticket", json=payload)
        ticket_id = result.get("id") if isinstance(result, dict) else None
        if isinstance(ticket_id, int):
            ticket_id = str(ticket_id)
        if not isinstance(ticket_id, str) or not ticket_id.isdigit():
            raise GLPIError("glpi_ticket_create_id_missing")
        return ticket_id

    def update_ticket(self, ticket_id, fields):
        """Update a GLPI ticket using the REST API input envelope."""
        if not str(ticket_id).isdigit():
            raise ValueError("invalid_glpi_ticket_id")
        if not isinstance(fields, dict) or not fields:
            raise ValueError("ticket_fields_required")
        return self._call("PUT", "Ticket/" + str(ticket_id),
                          json={"input": fields})

    def find_ticket_for_run(self, run_id):
        """Return the unique ticket whose title explicitly contains this Run ID."""
        if not isinstance(run_id, str) or not run_id.startswith("RUN-"):
            raise ValueError("invalid_run_id")
        result = self.search_tickets(run_id, limit=100)
        data = result.get("data", []) if isinstance(result, dict) else []
        rows = list(data.values()) if isinstance(data, dict) else data
        matches = []
        for row in rows if isinstance(rows, list) else []:
            if not isinstance(row, dict):
                continue
            name = str(row.get("2", row.get("name", "")))
            ticket_id = row.get("1", row.get("id"))
            if run_id in name and str(ticket_id).isdigit():
                matches.append(str(ticket_id))
        matches = sorted(set(matches))
        if len(matches) > 1:
            raise GLPIError("multiple_glpi_tickets_for_run")
        return matches[0] if matches else None
