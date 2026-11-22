"""Synthetic, fail-closed DecisionEvidence verification. Not production authorization.

Caller supplies backend-authenticated context and a trusted key mapping; neither
is read from the untrusted envelope. Nonce reservation is SQLite-transactional.
No callback, host action, or external service is invoked.
"""
import hashlib
import hmac
import json
import sqlite3

MAX_ENVELOPE_BYTES = 8192
MAX_FIELD_CHARS = 256

FIELDS = ("schema_version", "tenant_id", "principal_id", "event_id",
          "resource_id", "twin_revision", "evidence_digest", "policy_version",
          "decision", "approval_id", "issued_at", "expires_at", "nonce", "issuer_key_id")

def canonical(envelope):
    if not isinstance(envelope, dict) or set(envelope) != set(FIELDS):
        raise ValueError("envelope_fields")
    for name, value in envelope.items():
        if isinstance(value, str) and (len(value) > MAX_FIELD_CHARS or any(ord(c) < 32 or ord(c) == 127 for c in value)):
            raise ValueError("field_bounds")
    raw = json.dumps(envelope, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    if len(raw) > MAX_ENVELOPE_BYTES:
        raise ValueError("envelope_bounds")
    return raw

def sign_fixture(envelope, key):
    """Test helper ONLY; not a production signing interface."""
    return hmac.new(key, canonical(envelope), hashlib.sha256).hexdigest()

def verify_and_consume(db, *, envelope, mac, backend, trusted_keys, now):
    """Return DENY or SIMULATE_ONLY; atomic single-use nonce with no production ALLOW.

    Database must be owned by this verifier (autocommit, no active transaction).
    The caller must supply a backend-authenticated context and an independently
    trusted keyring. The fixture keyring is NOT a production trust service.
    """
    begun = False
    try:
        if not isinstance(backend, dict) or not isinstance(trusted_keys, dict):
            return {"decision": "DENY", "reason": "context"}
        if not isinstance(now, int) or isinstance(now, bool):
            return {"decision": "DENY", "reason": "clock"}
        raw = canonical(envelope)
        for field in FIELDS:
            value = envelope[field]
            if field not in ("issued_at", "expires_at") and (not isinstance(value, str) or not value):
                return {"decision": "DENY", "reason": "fields"}
        if envelope["schema_version"] != "v1-synthetic" or envelope["decision"] != "SIMULATE_ONLY":
            return {"decision": "DENY", "reason": "decision"}
        if any(not isinstance(envelope[f], int) or isinstance(envelope[f], bool)
               for f in ("issued_at", "expires_at")):
            return {"decision": "DENY", "reason": "time"}
        if not (envelope["issued_at"] <= now < envelope["expires_at"] and
                0 < envelope["expires_at"] - envelope["issued_at"] <= 300):
            return {"decision": "DENY", "reason": "expired"}
        if len(envelope["evidence_digest"]) != 64 or any(c not in "0123456789abcdef" for c in envelope["evidence_digest"]):
            return {"decision": "DENY", "reason": "digest"}
        required = ("tenant_id", "principal_id", "event_id", "resource_id",
                    "twin_revision", "evidence_digest", "policy_version", "approval_id")
        if any(not isinstance(backend.get(f), str) or
               not hmac.compare_digest(envelope[f], backend[f]) for f in required):
            return {"decision": "DENY", "reason": "binding"}
        key = trusted_keys.get(envelope["issuer_key_id"])
        if not isinstance(key, bytes) or len(key) < 32 or not isinstance(mac, str):
            return {"decision": "DENY", "reason": "key"}
        expected = hmac.new(key, raw, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, mac):
            return {"decision": "DENY", "reason": "signature"}
        if db.in_transaction:
            return {"decision": "DENY", "reason": "transaction"}
        db.execute("BEGIN IMMEDIATE")
        begun = True
        db.execute("INSERT INTO consumed_nonces(issuer_key_id, tenant_id, nonce) VALUES (?,?,?)",
                   (envelope["issuer_key_id"], envelope["tenant_id"], envelope["nonce"]))
        db.commit()
        begun = False
        return {"decision": "SIMULATE_ONLY", "production_authorized": False,
                "nonce_consumed": True}
    except (sqlite3.Error, ValueError, TypeError, KeyError, AttributeError):
        return {"decision": "DENY", "reason": "invalid_or_replayed"}
    finally:
        if begun:
            db.rollback()
