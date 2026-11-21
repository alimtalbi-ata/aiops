"""Synthetic independently witnessed Twin/Evidence transaction receipt (ADR-003).

The witness is a separate trust boundary from fetch_pair. HMAC here is only
a deterministic test fixture, NOT a production backend attestation.
A backend-provided snapshot_id alone never passes this gate.
"""
from dataclasses import dataclass
import hashlib
import hmac
import json
from resource_binding import _identifier, _scope, _digest
from snapshot_pair import SnapshotPair, snapshot_pair_decision


@dataclass(frozen=True)
class AttestedPair:
    pair: SnapshotPair
    twin_revision: str
    evidence_revision: str
    receipt: str


def _message(event, revision):
    return json.dumps(
        [event[k] for k in ("tenant", "instance", "event", "digest",
                            "twin_identifier", "evidence_identifier", "snapshot_id")] +
        [revision], separators=(",", ":"), ensure_ascii=True).encode("ascii")


class SyntheticIndependentWitness:
    """Test-only verifier: secret must never be available to adapter under test."""
    def __init__(self, key):
        if not isinstance(key, bytes) or len(key) < 32:
            raise ValueError("fixture key")
        self._key = key

    def issue_fixture_receipt(self, event, revision):
        _identifier(revision)
        return hmac.new(self._key, _message(event, revision), hashlib.sha256).hexdigest()

    def verify(self, event, revision, receipt):
        if not isinstance(receipt, str) or len(receipt) != 64:
            return False
        try:
            _identifier(revision)
            _scope(event["tenant"])
            _scope(event["instance"])
            _identifier(event["event"])
            _digest(event["digest"])
            for field in ("twin_identifier", "evidence_identifier", "snapshot_id"):
                _identifier(event[field])
            if any(c not in "0123456789abcdef" for c in receipt):
                return False
            return hmac.compare_digest(self.issue_fixture_receipt(event, revision), receipt)
        except (KeyError, TypeError, ValueError, PermissionError, UnicodeError):
            return False


def attested_snapshot_decision(*, event, assertion, verifier, fetch_pair, witness):
    """Deny first; no real ALLOW or mutation, even with a valid fixture receipt."""
    if not isinstance(event, dict) or not callable(getattr(witness, "verify", None)):
        return "DENY"

    def checked_fetch_pair(**kwargs):
        response = fetch_pair(**kwargs)
        if not isinstance(response, AttestedPair):
            raise PermissionError("missing independent receipt")
        if (not isinstance(response.pair, SnapshotPair) or
                response.twin_revision != response.evidence_revision or
                response.twin_revision != kwargs["snapshot_id"] or
                not witness.verify(event, response.twin_revision, response.receipt)):
            raise PermissionError("invalid transaction receipt")
        return response.pair

    try:
        return snapshot_pair_decision(event=event, assertion=assertion,
                                      verifier=verifier, fetch_pair=checked_fetch_pair)
    except (PermissionError, ValueError, TypeError, AttributeError, KeyError):
        return "DENY"
