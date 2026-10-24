"""Strict offline/loopback parsing of Checkmk Livestatus service rows.

Read-only query; not a production monitoring integration or authentication proof.
"""
from __future__ import annotations
import json
import socket
from demo.noc_checkmk_export import parse_host_status_export
from demo.noc_livestatus_loopback import MAX_BYTES

SERVICES_QUERY=b"GET services\nColumns: host_name description state plugin_output\nOutputFormat: json\n\n"

def parse_services(payload:list, *, captured_at:str, now_utc:str)->dict:
    if not isinstance(payload,list) or len(payload)<2 or payload[0]!=["host_name","description","state","plugin_output"] or len(payload)>501:
        raise ValueError("unexpected Livestatus services table")
    names=set();services=[]
    for item in payload[1:]:
        if not isinstance(item,list) or len(item)!=4:
            raise ValueError("unexpected service record")
        host,description,state,output=item
        if not isinstance(host,str) or not isinstance(description,str) or not host or not description or len(description)>128:
            raise ValueError("invalid service identity")
        key=(host,description)
        if key in names:
            raise ValueError("duplicate service")
        names.add(key)
        if type(state) is not int or state not in (0,1,2,3):
            raise ValueError("unrecognized service state")
        services.append({"host":host,"description":description,"state":state,"output":output})
    # Reuse existing strict time, host-name, output and provenance validation,
    # including rejection of future/stale captures.
    proxy={"schema":"aiops-checkmk-host-export-v1","source":"CHECKMK_EXPORT",
           "read_only":True,"live_remediation_authorized":False,"captured_at":captured_at,
           "hosts":[{"name":row["host"],"state":row["state"],"output":row["output"]} for row in services]}
    # Host repetition is normal when an asset has multiple services. Validate
    # each row separately, rather than dropping distinct service identities.
    normalized=[]
    for row in proxy["hosts"]:
        single=dict(proxy,hosts=[row])
        normalized.append(next(iter(parse_host_status_export(single,now_utc=now_utc)["hosts"].values())))
    result=parse_host_status_export(dict(proxy,hosts=[{"name":services[0]["host"],"state":services[0]["state"],"output":services[0]["output"]}]),now_utc=now_utc)
    return {"schema":"aiops-checkmk-services-loopback-v1","captured_at":captured_at,
            "age_seconds":result["age_seconds"],
            "services":[{"host":row["host"],"description":row["description"],
                         "state":normal["state"],"output":normal["output"]}
                        for row,normal in zip(services,normalized)],
            "provenance":"LOOPBACK_UNVERIFIED","runtime_authenticated":False,
            "live_remediation_authorized":False}

def collect_loopback_services(*,host:str,port:int,captured_at:str,now_utc:str,timeout:float=2.0)->dict:
    if host not in ("127.0.0.1","::1") or type(port) is not int or not 1<=port<=65535:
        raise ValueError("loopback only")
    if type(timeout) not in (float,int) or not 0.1<=timeout<=5:
        raise ValueError("invalid timeout")
    family=socket.AF_INET6 if host=="::1" else socket.AF_INET
    with socket.socket(family,socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout)
        sock.connect((host,port))
        sock.sendall(SERVICES_QUERY)
        blocks=[];size=0
        while True:
            chunk=sock.recv(min(8192,MAX_BYTES+1-size))
            if not chunk:break
            size+=len(chunk)
            if size>MAX_BYTES:raise ValueError("oversized Livestatus reply")
            blocks.append(chunk)
    return parse_services(json.loads(b"".join(blocks).decode("utf-8")),captured_at=captured_at,now_utc=now_utc)
