"""In-memory session prototype; not wired to HTTP or production authentication.

Only a trusted identity adapter may issue sessions. Membership must be
revalidated externally on every protected read. Multi-worker deployment
requires a shared atomic store; process restart revokes all prototype sessions.
"""
import hashlib
import secrets
import threading
import time
from dataclasses import dataclass

from portal.incident_read_policy import IncidentReadPrincipal, may_read_incident


@dataclass
class _Session:
    principal: IncidentReadPrincipal
    issued: float
    touched: float


class OperatorSessions:
    def __init__(self, clock=time.monotonic):
        self._clock = clock
        self._lock = threading.Lock()
        self._sessions = {}
        self.idle_seconds = 900
        self.absolute_seconds = 28800
        self.capacity = 10000

    @staticmethod
    def _key(token):
        if not isinstance(token, str) or len(token) != 43 or not token.isascii():
            return None
        return hashlib.sha256(token.encode("ascii")).digest()

    def _expired(self, session, now):
        return (now < session.touched or now - session.touched >= self.idle_seconds
                or now - session.issued >= self.absolute_seconds)

    def issue(self, principal):
        if type(principal) is not IncidentReadPrincipal or not may_read_incident(principal, principal.tenant):
            raise ValueError("unqualified principal")
        with self._lock:
            now = self._clock()
            for key, session in list(self._sessions.items()):
                if self._expired(session, now):
                    del self._sessions[key]
            if len(self._sessions) >= self.capacity:
                raise RuntimeError("session capacity reached")
            token = secrets.token_urlsafe(32)
            self._sessions[self._key(token)] = _Session(principal, now, now)
            return token

    def resolve(self, token):
        key = self._key(token)
        with self._lock:
            session = self._sessions.get(key)
            if session is None:
                return None
            now = self._clock()
            if self._expired(session, now):
                del self._sessions[key]
                return None
            session.touched = now
            return session.principal

    def revoke(self, token):
        with self._lock:
            self._sessions.pop(self._key(token), None)
