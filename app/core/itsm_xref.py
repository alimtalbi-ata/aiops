"""Core authoritative read-only ITSM xref. No GLPI writes or ticket-text inference."""
from __future__ import annotations
import os, re, json, hmac, hashlib, stat
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Header, Query
from fastapi.responses import JSONResponse
from shared.db import db

router = APIRouter()
SCHEMA = "aiops.core-itsm-xref-read.v1"
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{1,95}\Z", re.ASCII)
_TICKET = re.compile(r"[1-9][0-9]{0,17}\Z", re.ASCII)
_RUN = re.compile(r"RUN-[A-Za-z0-9_-]{1,96}\Z", re.ASCII)
_INC = re.compile(r"INC-[A-Za-z0-9_-]{1,96}\Z", re.ASCII)
_HEX = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)
_FIELDS = ("association_id","tenant_id","glpi_instance_id","ticket_id","glpi_entity_id",
           "incident_id","run_id","source_event_id","mapping_version","event_type","actor_id",
           "observed_at","known_at","supersedes_association_id","verification_method",
           "provenance","glpi_ticket_readback_verified","core_run_readback_verified","source_payload_hash")
_COLUMNS = _FIELDS + ("attestation_mac",)
_HEADERS = {"Cache-Control":"no-store","Pragma":"no-cache","X-Content-Type-Options":"nosniff"}

def _reply(code, status="UNKNOWN", **fields):
    headers = dict(_HEADERS)
    if code == 401: headers["WWW-Authenticate"] = "Bearer"
    return JSONResponse({"schema":SCHEMA,"status":status,**fields},status_code=code,headers=headers)

def _valid(value, pattern=_ID):
    return isinstance(value,str) and pattern.fullmatch(value) is not None

def _utc(value):
    if not isinstance(value,datetime) or value.tzinfo is None or value.utcoffset() is None: return None
    try:
        out = value.astimezone(timezone.utc)
        return out if 1970 <= out.year < 9999 else None
    except (OverflowError,ValueError): return None

def _stamp(value):
    out = _utc(value)
    return out.isoformat(timespec="microseconds") if out else None

def _payload(row):
    return json.dumps({"v":1,"xref":{k:_stamp(row[k]) if k in ("observed_at","known_at") else row[k] for k in _FIELDS}},
                      sort_keys=True,separators=(",",":"),ensure_ascii=True).encode("ascii")

def _signed(row,key):
    try:
        mac = row["attestation_mac"]
        return _valid(mac,_HEX) and hmac.compare_digest(mac,hmac.new(key,_payload(row),hashlib.sha256).hexdigest())
    except (KeyError,TypeError,ValueError): return False

def _owner_proof_payload(kind, resource_id, tenant_id, verified, source_event_id, observed_at, known_at):
    """Canonical v1 ownership proof, independent of the xref event MAC."""
    return json.dumps({"v":1,"kind":kind,"resource_id":resource_id,"tenant_id":tenant_id,
                       "verified":verified,"source_event_id":source_event_id,
                       "observed_at":_stamp(observed_at),"known_at":_stamp(known_at)},
                      sort_keys=True,separators=(",",":"),ensure_ascii=True).encode("ascii")

def _owners_attested(owned):
    """Fail closed unless a separately keyed, deployment-owned proof exists for all five CIs.

    This is only a cryptographic integrity gate. The producer MUST authenticate
    GLPI/Core and tenant scope before signing; CI fixture signatures do not prove GLPI.
    """
    key=os.getenv("AIOPS_XREF_OWNER_ATTESTATION_KEY","")
    path=os.getenv("AIOPS_XREF_OWNER_PROOFS_PATH","")
    if not (isinstance(key,str) and key.isascii() and 32<=len(key)<=256
            and isinstance(path,str) and os.path.isabs(path)):
        return False
    try:
        info=os.stat(path,follow_symlinks=False)
        if not stat.S_ISREG(info.st_mode) or info.st_size>65536: return False
        with open(path,encoding="utf-8") as source:
            manifest=json.load(source)
        if not isinstance(manifest,dict) or set(manifest)!={"schema","proofs"}:
            return False
        if manifest["schema"]!="aiops.core-ownership-proof.v1": return False
        proofs=manifest["proofs"]
        if not isinstance(proofs,dict) or len(proofs)>256: return False
        for kind,rid,tenant,verified,source_id,observed,known in owned:
            name=kind+"|"+rid
            mac=proofs.get(name)
            if not _valid(mac,_HEX): return False
            expected=hmac.new(key.encode("ascii"),
                              _owner_proof_payload(kind,rid,tenant,verified,source_id,observed,known),
                              hashlib.sha256).hexdigest()
            if not hmac.compare_digest(mac,expected): return False
        return True
    except (OSError,UnicodeError,ValueError,TypeError,KeyError):
        return False


def _glpi_readback(e, tenant, instance, ticket):
    """Independent GLPI REST read: ticket, entity and at least one attached CI.

    Credentials are server-held and pinned to an exact tenant/instance/HTTPS
    origin. This is NOT an actor OIDC grant or proof of a GLPI-to-Run relation;
    the separate signed association and Core Run/Incident checks remain mandatory.
    Fail closed on any absent/ambiguous/stale source or transport failure.
    """
    from urllib.parse import urlsplit
    import requests

    raw = os.getenv("AIOPS_XREF_GLPI_READBACK_JSON", "")
    if not raw or len(raw) > 16384:
        return False
    try:
        configs = json.loads(raw)
        if not isinstance(configs, list) or not 1 <= len(configs) <= 16:
            return False
        matches = [c for c in configs if isinstance(c, dict)
                   and c.get("tenant_id") == tenant and c.get("instance_id") == instance]
        if len(matches) != 1:
            return False
        cfg = matches[0]
        if set(cfg) != {"tenant_id", "instance_id", "origin", "app_token", "session_token"}:
            return False
        origin = cfg["origin"]
        if not isinstance(origin, str) or len(origin) > 256:
            return False
        parsed = urlsplit(origin)
        if (parsed.scheme != "https" or not parsed.hostname or parsed.username
                or parsed.password or parsed.query or parsed.fragment
                or parsed.path not in ("", "/") or origin.rstrip("/") !=
                parsed.geturl().rstrip("/")):
            return False
        if any(not isinstance(cfg[k], str) or not 16 <= len(cfg[k]) <= 512
               or any(ch in cfg[k] for ch in "\r\n") for k in ("app_token", "session_token")):
            return False
        if not _valid(tenant) or not _valid(instance) or not _valid(ticket, _TICKET):
            return False
        entity_id = e["glpi_entity_id"]
        if not re.fullmatch(r"[0-9]{1,18}", entity_id):
            return False

        headers = {"App-Token": cfg["app_token"],
                   "Session-Token": cfg["session_token"], "Accept": "application/json"}
        base = origin.rstrip("/") + "/apirest.php"

        def read(session, path):
            # No redirects, ambient proxy credentials, unbounded responses or
            # caller-controlled URLs. TLS verification remains enabled.
            with session.get(base + path, headers=headers, timeout=(2, 3),
                             allow_redirects=False, stream=True, verify=True) as response:
                if response.status_code != 200:
                    raise ValueError("GLPI read refused")
                content_type = response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
                if content_type != "application/json":
                    raise ValueError("GLPI content type")
                data = bytearray()
                for chunk in response.iter_content(chunk_size=4096):
                    data.extend(chunk)
                    if len(data) > 65536:
                        raise ValueError("GLPI response too large")
                return json.loads(data.decode("utf-8"))

        def exact_number(value, expected):
            return type(value) is int and str(value) == expected

        with requests.Session() as session:
            session.trust_env = False
            ticket_data = read(session, "/Ticket/" + ticket)
            if (not isinstance(ticket_data, dict)
                    or not exact_number(ticket_data.get("id"), ticket)
                    or not exact_number(ticket_data.get("entities_id"), entity_id)):
                return False
            entity = read(session, "/Entity/" + entity_id)
            if not isinstance(entity, dict) or not exact_number(entity.get("id"), entity_id):
                return False
            items = read(session, "/Ticket/" + ticket + "/Item_Ticket")
            if not isinstance(items, list) or not 1 <= len(items) <= 32:
                return False
            allowed = {"Computer", "NetworkEquipment", "Server", "Monitor",
                       "Printer", "Phone", "Peripheral"}
            seen = set()
            for item in items:
                if not isinstance(item, dict) or item.get("itemtype") not in allowed:
                    return False
                ci_id = item.get("items_id")
                if type(ci_id) is not int or ci_id < 1:
                    return False
                pair = (item["itemtype"], ci_id)
                if pair in seen:
                    return False
                seen.add(pair)
                ci = read(session, "/" + pair[0] + "/" + str(ci_id))
                if (not isinstance(ci, dict)
                        or not exact_number(ci.get("id"), str(ci_id))
                        or not exact_number(ci.get("entities_id"), entity_id)):
                    return False
        return True
    except (OSError, ValueError, TypeError, KeyError, UnicodeError, requests.RequestException):
        return False

def _auth(header):
    """Server-only digest ACL; never use shared ADMIN or caller actor/tenant claims."""
    raw = os.getenv("AIOPS_XREF_READ_AUTHZ_JSON","")
    if not raw or len(raw)>16384: return None,503
    try:
        entries=json.loads(raw)
        if not isinstance(entries,list) or not 0<len(entries)<=64: raise ValueError()
        seen=set()
        for e in entries:
            if (not isinstance(e,dict) or set(e)!={"token_sha256","actor_id","tenant_ids","permissions"}
                or not _valid(e["token_sha256"],_HEX) or e["token_sha256"] in seen
                or not _valid(e["actor_id"]) or not isinstance(e["tenant_ids"],list) or not e["tenant_ids"]
                or not all(_valid(t) for t in e["tenant_ids"])
                or not isinstance(e["permissions"],list)
                or not all(isinstance(p,str) and len(p)<=80 for p in e["permissions"])): raise ValueError()
            seen.add(e["token_sha256"])
    except (ValueError,KeyError,TypeError): return None,503
    scheme,sep,token=(header or "").partition(" ")
    if scheme.lower()!="bearer" or not sep or not token or len(token)>512 or any(c.isspace() for c in token):
        return None,401
    digest=hashlib.sha256(token.encode()).hexdigest()
    matches=[e for e in entries if hmac.compare_digest(digest,e["token_sha256"])]
    return (matches[0],200) if len(matches)==1 else (None,401)

def _key():
    key=os.getenv("AIOPS_XREF_ATTESTATION_KEY","")
    return key.encode("ascii") if isinstance(key,str) and 32<=len(key)<=256 and key.isascii() else None

def _evaluate(c,rows,tenant,instance,ticket,key,now):
    if not rows: return "NOT_FOUND",None
    if len(rows)>32: return "CONFLICT",None
    previous=None
    for record in rows:
        e=dict(zip(_COLUMNS,record))
        v=e["mapping_version"]
        if (type(v) is not int or v<1
            # An immutable history must begin at version 1. A lone version 2
            # with no predecessor is not an authoritative read-back.
            or (previous is None and (v!=1 or e["supersedes_association_id"] is not None))
            or (previous is not None and (v!=previous["mapping_version"]+1 or
                e["supersedes_association_id"]!=previous["association_id"]))): return "CONFLICT",None
        if (e["tenant_id"]!=tenant or e["glpi_instance_id"]!=instance or e["ticket_id"]!=ticket
            or not all(_valid(e[k]) for k in ("association_id","source_event_id","actor_id"))
            or not isinstance(e["glpi_entity_id"],str) or not re.fullmatch(r"[0-9]{1,18}",e["glpi_entity_id"])
            or not _valid(e["run_id"],_RUN) or not _valid(e["incident_id"],_INC)
            or e["event_type"] not in ("VERIFIED","REVOKED")
            or e["verification_method"]!="AUTHENTICATED_ID_READBACK"
            or e["provenance"]!="AUTHENTICATED_SOURCE_API"
            or e["glpi_ticket_readback_verified"] is not True
            or e["core_run_readback_verified"] is not True
            or not _valid(e["source_payload_hash"],_HEX) or not _signed(e,key)): return "UNKNOWN",None
        # Verify every signed historical event, not just the terminal row.
        # A fresh v2 must not launder a future-dated or time-reversed v1.
        observed,known=_utc(e["observed_at"]),_utc(e["known_at"])
        if observed is None or known is None: return "UNKNOWN",None
        if observed>known or observed>now or known>now: return "CONFLICT",None
        # A superseding source observation cannot precede the event it supersedes.
        # Later ingestion alone must not turn an out-of-order observation into VERIFIED.
        if previous is not None and (known<_utc(previous["known_at"]) or
                                     observed<_utc(previous["observed_at"])):
            return "CONFLICT",None
        previous=e
    e=previous
    if e["event_type"]=="REVOKED": return "UNKNOWN",None
    observed,known=_utc(e["observed_at"]),_utc(e["known_at"])
    if now-observed>timedelta(minutes=5) or now-known>timedelta(minutes=5): return "STALE",None
    core=c.execute("select r.incident_id,i.incident_id from aiops.runs r join aiops.incidents i "
                   "on i.incident_id=r.incident_id where r.run_id=%s",(e["run_id"],)).fetchone()
    if not core or core!=(e["incident_id"],e["incident_id"]): return "UNKNOWN",None
    resources=(("incident",e["incident_id"]),("run",e["run_id"]),("glpi_instance",instance),
               ("glpi_ticket",instance+":"+ticket),("glpi_entity",instance+":"+e["glpi_entity_id"]))
    owned=c.execute("select resource_kind,resource_id,tenant_id,verified,source_event_id,observed_at,known_at "
                    "from aiops.tenant_resource_ownership "
                    "where (resource_kind,resource_id) in ((%s,%s),(%s,%s),(%s,%s),(%s,%s),(%s,%s))",
                    tuple(x for pair in resources for x in pair)).fetchall()
    found={(kind,rid):(t,verified,source_event_id,observed_at,known_at)
           for kind,rid,t,verified,source_event_id,observed_at,known_at in owned}
    if len(found)!=len(resources): return "UNKNOWN",None
    if any(found[r][0]!=tenant for r in resources): return "UNAUTHORIZED",None
    if any(found[r][1] is not True for r in resources): return "UNKNOWN",None
    # Ownership is an independent, immutable attestation. Validate its source
    # identity and temporal integrity, but do not apply the short-lived xref
    # freshness window: immutable ownership rows cannot be refreshed in place.
    for r in resources:
        _,_,source_id,owner_observed,owner_known=found[r]
        observed,known=_utc(owner_observed),_utc(owner_known)
        if not _valid(source_id) or observed is None or known is None:
            return "UNKNOWN",None
        if observed>known or known>now:
            return "CONFLICT",None
    # Ownership rows alone are not an independent tenant/GLPI attestation.
    # No attestor configured => UNKNOWN, even for a fully signed xref event.
    if not _owners_attested(owned): return "UNKNOWN",None
    # HMAC fixture/verified=true is never a substitute for independently
    # authenticated, tenant-scoped GLPI Ticket/Entity/CI source readback.
    if not _glpi_readback(e, tenant, instance, ticket): return "UNKNOWN",None
    return "VERIFIED",e

@router.get("/api/tenants/{tenant_id}/itsm/glpi/{instance_id}/tickets/{ticket_id}/xref")
def read_ticket_xref(tenant_id:str,instance_id:str,ticket_id:str,
                     authorization:str|None=Header(default=None),
                     expected_run_id:str|None=Query(default=None),
                     expected_incident_id:str|None=Query(default=None),
                     evidence_known_at:str|None=Query(default=None)):
    now=datetime.now(timezone.utc)
    if (not (_valid(tenant_id) and _valid(instance_id) and _valid(ticket_id,_TICKET))
        or (expected_run_id is not None and not _valid(expected_run_id,_RUN))
        or (expected_incident_id is not None and not _valid(expected_incident_id,_INC))):
        return _reply(404)
    stale_evidence = False
    if evidence_known_at is not None:
        try:
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})",evidence_known_at):
                return _reply(404)
            stamp=evidence_known_at[:-1]+"+00:00" if evidence_known_at.endswith("Z") else evidence_known_at
            when=_utc(datetime.fromisoformat(stamp))
            if when is None or when>now: return _reply(404)
            stale_evidence = now-when>timedelta(minutes=5)
        except (TypeError,ValueError,OverflowError): return _reply(404)
    actor,code=_auth(authorization)
    if code!=200: return _reply(code)
    if "itsm:xref:read" not in actor["permissions"] or tenant_id not in actor["tenant_ids"]:
        return _reply(403,"UNAUTHORIZED")
    # Never return a 200 STALE response before service authentication and
    # server-side tenant/permission authorization. This preflight still
    # guarantees zero DB calls for stale evidence.
    if stale_evidence: return _reply(200,"STALE")
    key=_key()
    if key is None: return _reply(503)
    try:
        with db() as c:
            rows=c.execute("select "+",".join(_COLUMNS)+" from aiops.itsm_xref_events "
                           "where tenant_id=%s and glpi_instance_id=%s and ticket_id=%s "
                           "order by mapping_version asc limit 33",(tenant_id,instance_id,ticket_id)).fetchall()
            status,e=_evaluate(c,rows,tenant_id,instance_id,ticket_id,key,now)
    except Exception: return _reply(503)
    if status=="NOT_FOUND": return _reply(404)
    if status=="UNAUTHORIZED": return _reply(403,"UNAUTHORIZED")
    if status!="VERIFIED": return _reply(200,status)
    if ((expected_run_id is not None and e["run_id"]!=expected_run_id)
        or (expected_incident_id is not None and e["incident_id"]!=expected_incident_id)):
        return _reply(200)
    return _reply(200,"VERIFIED",tenant_id=tenant_id,glpi_instance_id=instance_id,
                  ticket_id=ticket_id,incident_id=e["incident_id"],run_id=e["run_id"],
                  source_system="GLPI",source_event_id=e["source_event_id"],
                  association_id=e["association_id"],mapping_version=e["mapping_version"],
                  verification_method=e["verification_method"],tenant_acl_qualified=True,
                  glpi_ticket_readback_verified=True,core_run_readback_verified=True,
                  observed_at=_stamp(e["observed_at"]),known_at=_stamp(e["known_at"]),
                  provenance=e["provenance"])

# Core-owned actor ACL preflight; shares the existing xref router registration.
from core.actor_resource_authz import router as actor_resource_router
router.include_router(actor_resource_router)


# Core-owned REJECT-only delivery routes; no Worker/Policy implementation here.
from core.hitl_reject_delivery import router as hitl_reject_delivery_router
router.include_router(hitl_reject_delivery_router)
