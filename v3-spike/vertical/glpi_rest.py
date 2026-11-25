"""Read-only GLPI legacy REST client for an isolated synthetic lab."""
import json
import re
import urllib.request

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        return None

class LabGLPI:
    def __init__(self,port,app_token,user_token):
        if type(port) is not int or not 1024<=port<=65535 or port in (7770,7777,7790):
            raise ValueError("invalid lab port")
        for token in (app_token,user_token):
            if not isinstance(token,str) or not re.fullmatch(r"[A-Za-z0-9_-]{16,128}",token):
                raise ValueError("invalid token")
        self.base=f"http://127.0.0.1:{port}/apirest.php/"
        self.app_token=app_token
        self.user_token=user_token
        self.session=None
        self.opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
    def _get(self,path,headers):
        req=urllib.request.Request(self.base+path,headers={"App-Token":self.app_token,**headers})
        with self.opener.open(req,timeout=5) as response:
            raw=response.read(65537)
            if len(raw)>65536 or response.status!=200:
                raise ValueError("invalid GLPI response")
            return json.loads(raw)
    def __enter__(self):
        token=self._get("initSession",{"Authorization":"user_token "+self.user_token})["session_token"]
        if not isinstance(token,str) or not re.fullmatch(r"[A-Za-z0-9_-]{16,128}",token):
            raise ValueError("invalid session")
        self.session=token
        return self
    def __exit__(self,*args):
        try:
            if self.session: self._get("killSession",{"Session-Token":self.session})
        finally: self.session=None
    def read_ticket(self,tid):
        if type(tid) is not int or tid<=0 or not self.session:
            raise ValueError("invalid ticket or session")
        headers={"Session-Token":self.session}
        ticket=self._get(f"Ticket/{tid}",headers)
        if ticket.get("id")!=tid: raise ValueError("ticket mismatch")
        followups=self._get(f"Ticket/{tid}/ITILFollowup?range=0-19",headers)
        if not isinstance(followups,list) or len(followups)>20: raise ValueError("invalid followups")
        return ticket,followups
