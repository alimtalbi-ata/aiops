"""Bounded SQL contract for the not-yet-routed actor-scoped Core reader."""
import importlib.util
from pathlib import Path

import pytest

MODULE = Path(__file__).resolve().parents[1] / "app/core/portal_tenant_runs.py"
spec = importlib.util.spec_from_file_location("portal_tenant_runs_candidate", MODULE)
reader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reader)


class Cursor:
    def __init__(self, rows=()):
        self.rows = rows
        self.calls = []

    def execute(self, sql, params):
        self.calls.append((sql, params))
        return self

    def fetchall(self):
        return self.rows


def test_actor_query_is_parameterized_revocation_aware_and_bounded():
    cursor = Cursor([("RUN-1", None, "DEMO", "SCN", "FAILED", 1, 0, None, None, None)])
    result = reader.read_runs_for_verified_actor(cursor, actor_id="verified:actor-1", limit=17)
    assert [x["run_id"] for x in result["items"]] == ["RUN-1"]
    assert len(cursor.calls) == 1
    sql, params = cursor.calls[0]
    assert params == ("verified:actor-1", 17)
    assert "join aiops.portal_run_tenant_bindings" in sql
    assert "join aiops.portal_actor_tenant_grants" in sql
    assert "g.revoked_at is null" in sql
    assert "g.actor_id = %s" in sql
    assert "limit %s" in sql


@pytest.mark.parametrize("actor", ["", " ", "actor'; drop table runs;--", None, "a" * 201])
def test_unverified_or_malformed_actor_never_queries(actor):
    cursor = Cursor()
    with pytest.raises(ValueError):
        reader.read_runs_for_verified_actor(cursor, actor_id=actor)
    assert cursor.calls == []


@pytest.mark.parametrize("limit", [0, 101, -1, True, "100", 1.5])
def test_unbounded_or_invalid_limits_never_query(limit):
    cursor = Cursor()
    with pytest.raises(ValueError):
        reader.read_runs_for_verified_actor(cursor, actor_id="actor-1", limit=limit)
    assert cursor.calls == []


def test_empty_result_has_no_global_fallback():
    cursor = Cursor()
    assert reader.read_runs_for_verified_actor(cursor, actor_id="actor-1") == {"items": []}
    assert len(cursor.calls) == 1
