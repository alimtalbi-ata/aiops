"""FS147 cross-instance replay contract, SQLite fixture only (not Core integration)."""
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from threading import Lock

from worker.fs147_readonly_pipeline import FS147Request
from worker.fs147_verified_entrypoint import run_fs147_strict


def test_two_worker_instances_share_atomic_claim_and_never_repeat_bridge(tmp_path):
    """A restart/new process must not mistake UNKNOWN_TIMEOUT for a safe retry.

    SQLite is a test double for the Core-owned durable claim, not a proposed
    modification to Core or proof of its production transaction semantics.
    """
    database = tmp_path / "claims.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE claims (key TEXT PRIMARY KEY)")
    seen = []
    guard = Lock()
    request = FS147Request("tenant", "actor", "incident", "RUN-147-RESTART")

    def claim_once(key):
        # New connection on every call models independent Worker processes.
        with sqlite3.connect(database, timeout=5) as connection:
            try:
                connection.execute("INSERT INTO claims(key) VALUES (?)", (str(key),))
                return True
            except sqlite3.IntegrityError:
                return False

    def bridge(*_args):
        with guard:
            seen.append("bridge")
        raise TimeoutError("response lost; remote outcome unknown")

    def unexpected(*_args):
        raise AssertionError("downstream must never be called")

    def invoke():
        return run_fs147_strict(
            request, stop_auto=False, claim_once=claim_once,
            bridge_fetch=bridge, analyst_call=unexpected,
            critic_call=unexpected, policy_post=unexpected,
            now=lambda: datetime(2026, 11, 7, 12, tzinfo=timezone.utc),
        )

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: invoke(), range(8)))
    assert sorted(r["reason"] for r in results) == (
        ["DUPLICATE_RUN"] * 7 + ["UNKNOWN_TIMEOUT"]
    )
    assert all(r["status"] == "BLOCKED" and r["effect"] == "NO_EFFECT"
               and r["resolved"] is False for r in results)
    assert seen == ["bridge"]

    # A separate invocation with a fresh database connection simulates restart.
    restarted = invoke()
    assert restarted["reason"] == "DUPLICATE_RUN"
    assert restarted["effect"] == "NO_EFFECT"
    assert seen == ["bridge"]
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT COUNT(*) FROM claims").fetchone()[0] == 1
