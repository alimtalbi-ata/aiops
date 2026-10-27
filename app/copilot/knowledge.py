"""In-memory staging and ACL-first lexical retrieval for a future ACME RAG index.

No network fetching, embedding service, persistence, or LLM is used here.
Vendor material without reproduction rights is represented by metadata/links only.
"""
import hashlib
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

KINDS = frozenset({
    "vendor", "architecture", "implementation", "operations",
    "runbook", "postmortem", "incident", "cmdb",
})
RIGHTS = frozenset({"owned", "licensed", "link_only"})
INTERNAL_FACTS = frozenset({"architecture", "implementation", "operations", "incident", "cmdb", "postmortem"})
WORDS = re.compile(r"[^\W_]+", re.UNICODE)


def _date(value):
    if not isinstance(value, str):
        raise ValueError("UTC review date required")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timezone-aware review date required")
    return parsed.astimezone(timezone.utc)


def _required(doc, field):
    value = doc.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"missing {field}")
    return value.strip()


def stage_document(doc):
    """Validate rights/provenance before producing deterministic, non-persistent chunks."""
    if not isinstance(doc, dict):
        raise ValueError("document object required")
    kind = _required(doc, "kind")
    rights = _required(doc, "rights")
    if kind not in KINDS or rights not in RIGHTS:
        raise ValueError("unsupported kind or rights")
    fields = ("document_id", "title", "owner", "tenant_id", "product",
              "version", "source_uri", "reviewed_at")
    meta = {k: _required(doc, k) for k in fields}
    _date(meta["reviewed_at"])
    uri = urlsplit(meta["source_uri"])
    if kind == "vendor" and (uri.scheme != "https" or not uri.netloc):
        raise ValueError("vendor reference requires an HTTPS source URI")
    if kind != "vendor" and uri.scheme not in ("https", "acme"):
        raise ValueError("internal reference requires HTTPS or acme URI")
    roles = doc.get("acl_roles")
    if (not isinstance(roles, list) or not roles or
            any(not isinstance(role, str) or not role.strip() for role in roles)):
        raise ValueError("nonempty ACL roles required")
    body = doc.get("text", "")
    if not isinstance(body, str):
        raise ValueError("text must be a string")
    if rights == "link_only" and body.strip():
        raise ValueError("link-only documents cannot ingest copyrighted text")
    if rights != "link_only" and not body.strip():
        raise ValueError("licensed/owned documents require text")
    if len(body) > 1_000_000:
        raise ValueError("document too large for bounded staging")
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
    common = {
        **meta, "kind": kind, "rights": rights, "acl_roles": sorted(set(roles)),
        "content_sha256": digest,
        "untrusted_content": True,
    }
    if rights == "link_only":
        return [{**common, "chunk_id": f"{meta['document_id']}:link", "start": 0, "text": ""}]
    chunks = []
    # Deterministic bounded chunks with overlap; never interpret document instructions.
    for start in range(0, len(body), 400):
        segment = body[start:start + 450]
        chunks.append({
            **common,
            "chunk_id": f"{meta['document_id']}:{start}:{hashlib.sha256(segment.encode()).hexdigest()[:12]}",
            "start": start,
            "text": segment,
        })
    return chunks


def retrieve(question, chunks, *, tenant_id, roles, now=None,
             max_age_days=180, acme_facts_only=False, limit=5):
    """ACL/tenant/age filters precede keyword ranking and citation output."""
    if not tenant_id or not roles or not isinstance(roles, (list, tuple, set)):
        return []
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("timezone-aware current time required")
    if not isinstance(question, str) or not question.strip():
        return []
    tokens = {x.casefold() for x in WORDS.findall(question) if len(x) > 2}
    if not tokens:
        return []
    matches = []
    for c in chunks:
        if not isinstance(c, dict):
            continue
        if c.get("tenant_id") != tenant_id and not (
                c.get("kind") == "vendor" and c.get("tenant_id") == "GLOBAL"):
            continue
        if not set(c.get("acl_roles", [])).intersection(roles):
            continue
        if acme_facts_only and c.get("kind") not in INTERNAL_FACTS:
            continue
        try:
            reviewed = _date(c["reviewed_at"])
        except (KeyError, ValueError, TypeError):
            continue
        age = now.astimezone(timezone.utc) - reviewed
        if age < timedelta(0) or age > timedelta(days=max_age_days):
            continue
        haystack = " ".join([c.get("title", ""), c.get("product", ""), c.get("text", "")])
        score = len(tokens.intersection(x.casefold() for x in WORDS.findall(haystack)))
        if not score:
            continue
        matches.append((score, c))
    matches.sort(key=lambda p: (-p[0], p[1]["document_id"], p[1]["start"]))
    return [{
        "document_id": c["document_id"],
        "chunk_id": c["chunk_id"],
        "source_uri": c["source_uri"],
        "product": c["product"],
        "version": c["version"],
        "reviewed_at": c["reviewed_at"],
        "content_sha256": c["content_sha256"],
        "kind": c["kind"],
        "score_keyword": score,
        "excerpt_untrusted": c["text"][:220] if c["rights"] != "link_only" else "",
    } for score, c in matches[:max(0, min(limit, 20))]]
