"""Explicit-loopback-only Livestatus TCP reader for local integration tests.

Never connects to production. The Livestatus query contains only GET hosts.
"""
from __future__ import annotations
import json
import socket
from demo.noc_livestatus_import import normalize_livestatus_hosts

QUERY=b"GET hosts\nColumns: name state plugin_output\nOutputFormat: json\n\n"
MAX_BYTES=256_000

def collect_loopback_hosts(*,host:str,port:int,captured_at:str,now_utc:str,timeout:float=2.0)->dict:
    if host not in ("127.0.0.1","::1") or type(port) is not int or not 1<=port<=65535:
        raise ValueError("Livestatus requires literal loopback and valid port")
    if type(timeout) not in (float,int) or not 0.1<=timeout<=5:
        raise ValueError("invalid timeout")
    family=socket.AF_INET6 if host=="::1" else socket.AF_INET
    chunks=[]
    with socket.socket(family,socket.SOCK_STREAM) as connection:
        connection.settimeout(timeout)
        connection.connect((host,port))
        connection.sendall(QUERY)
        length=0
        while True:
            block=connection.recv(min(8192,MAX_BYTES+1-length))
            if not block:
                break
            chunks.append(block)
            length+=len(block)
            if length>MAX_BYTES:
                raise ValueError("Livestatus response exceeds limit")
    payload=json.loads(b"".join(chunks).decode("utf-8"))
    if not isinstance(payload,list) or not payload or payload[0]!=["name","state","plugin_output"]:
        raise ValueError("unexpected Livestatus header")
    rows=[]
    for row in payload[1:]:
        if not isinstance(row,list) or len(row)!=3:
            raise ValueError("unexpected Livestatus record")
        rows.append({"name":row[0],"state":row[1],"plugin_output":row[2]})
    result=normalize_livestatus_hosts(rows,captured_at=captured_at,now_utc=now_utc)
    result["collection_transport"]="TCP_LOOPBACK_ONLY"
    return result
