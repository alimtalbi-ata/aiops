"""Synthetic-only admission spike. Run: python event_store.py -v.
Requires jsonschema 4.26.0. Identity arguments must come from trusted caller.
Digest is declared, not a verified payload digest.
"""
import datetime as dt
import hashlib
import json
import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from jsonschema import Draft202012Validator, FormatChecker

SCHEMA = json.loads(Path(__file__).with_name("event.schema.json").read_text())
VALIDATOR = Draft202012Validator(SCHEMA, format_checker=FormatChecker())

def initialize(path):
    with sqlite3.connect(path) as db:
        db.execute("""CREATE TABLE IF NOT EXISTS events (
            tenant TEXT NOT NULL, instance TEXT NOT NULL, event TEXT NOT NULL,
            fingerprint TEXT NOT NULL, body TEXT NOT NULL,
            PRIMARY KEY (tenant, instance, event))""")

def admit(path, body, *, tenant, instance, now):
    VALIDATOR.validate(body)
    if (body["tenant"], body["instance"]) != (tenant, instance):
        raise PermissionError("source scope mismatch")
    age = (now - dt.datetime.fromisoformat(body["at"].replace("Z", "+00:00"))).total_seconds()
    # Late retries are rejected uniformly before lookup: no existence disclosure
    # or re-admission. Delivery retry belongs to a separate durable outbox.
    if not 0 <= age <= 300:
        raise ValueError("outside synthetic freshness window")
    key = (tenant, instance, body["event"])
    serialized = json.dumps(body, sort_keys=True, separators=(",", ":"))
    fingerprint = hashlib.sha256(serialized.encode()).hexdigest()
    with sqlite3.connect(path, timeout=10) as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT fingerprint FROM events WHERE tenant=? AND instance=? AND event=?", key).fetchone()
        if row:
            if row[0] != fingerprint:
                raise ValueError("identity conflict")
            return "DUPLICATE"
        db.execute("INSERT INTO events VALUES (?,?,?,?,?)", (*key, fingerprint, serialized))
        return "ACCEPT"

def read(path, *, tenant, instance, event):
    # Trusted scope required; no authentication implementation in this spike.
    with sqlite3.connect(path) as db:
        row = db.execute("SELECT body FROM events WHERE tenant=? AND instance=? AND event=?", (tenant, instance, event)).fetchone()
    return json.loads(row[0]) if row else None

class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = str(Path(self.tmp.name) / "events.sqlite")
        initialize(self.path)
        self.now = dt.datetime(2026,11,20,12,tzinfo=dt.timezone.utc)
        self.fixture = dict(tenant="demo-a", instance="collector-a", event="e1", domain="database", ci="db1", mode="SYNTHETIC", at="2026-11-20T12:00:00Z", digest="a"*64)

    def put(self, body=None, **scope):
        return admit(self.path, self.fixture if body is None else body, now=self.now, tenant=scope.get("tenant","demo-a"), instance=scope.get("instance","collector-a"))

    def test_composite_collision(self):
        self.assertEqual(self.put(dict(self.fixture, instance="collector-a:x"), instance="collector-a:x"), "ACCEPT")
        self.assertEqual(self.put(dict(self.fixture, event="x:e1")), "ACCEPT")

    def test_replay(self):
        self.assertEqual(self.put(), "ACCEPT")
        self.assertEqual(self.put(), "DUPLICATE")

    def test_conflict(self):
        self.put()
        with self.assertRaises(ValueError):
            self.put(dict(self.fixture, digest="b"*64))

    def test_concurrent_replay(self):
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda _: self.put(), range(16)))
        self.assertEqual(results.count("ACCEPT"), 1)
        self.assertEqual(results.count("DUPLICATE"), 15)

    def test_scope(self):
        with self.assertRaises(PermissionError):
            self.put(tenant="demo-b")
        with self.assertRaises(PermissionError):
            self.put(instance="other")
        self.put()
        self.assertIsNone(read(self.path, tenant="demo-b", instance="collector-a", event="e1"))
        self.assertIsNone(read(self.path, tenant="demo-a", instance="other", event="e1"))
        self.assertEqual(read(self.path, tenant="demo-a", instance="collector-a", event="e1"), self.fixture)

    def test_invalid(self):
        from jsonschema.exceptions import ValidationError
        for patch in (dict(ci=" "), dict(event="e1\n"), dict(digest="a"*64+"\n"), dict(mode="OBSERVED")):
            with self.subTest(patch=patch), self.assertRaises(ValidationError):
                self.put(dict(self.fixture, **patch))

    def test_freshness(self):
        for at in ("2026-11-20T11:54:59Z","2026-11-20T12:00:01Z"):
            with self.assertRaises(ValueError):
                self.put(dict(self.fixture, at=at))

    def test_retry_boundary_and_no_disclosure(self):
        self.put()
        for seconds, expected in ((300, "DUPLICATE"), (301, None)):
            now = self.now + dt.timedelta(seconds=seconds)
            if expected:
                self.assertEqual(admit(self.path, self.fixture, tenant="demo-a", instance="collector-a", now=now), expected)
            else:
                for body in (self.fixture, dict(self.fixture, event="unknown"), dict(self.fixture, digest="b"*64)):
                    with self.assertRaisesRegex(ValueError, "^outside synthetic freshness window$"):
                        admit(self.path, body, tenant="demo-a", instance="collector-a", now=now)
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM events").fetchone()[0], 1)
        self.assertEqual(read(self.path, tenant="demo-a", instance="collector-a", event="e1"), self.fixture)

    def test_concurrent_conflicting_digests(self):
        def attempt(digest):
            try:
                return self.put(dict(self.fixture, digest=digest))
            except ValueError as exc:
                self.assertEqual(str(exc), "identity conflict")
                return "CONFLICT"
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(attempt, ["a"*64, "b"*64]))
        self.assertCountEqual(results, ["ACCEPT", "CONFLICT"])
        with sqlite3.connect(self.path) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM events").fetchone()[0], 1)
        winner = ["a"*64, "b"*64][results.index("ACCEPT")]
        self.assertEqual(read(self.path, tenant="demo-a", instance="collector-a", event="e1")["digest"], winner)

if __name__ == "__main__":
    unittest.main()
