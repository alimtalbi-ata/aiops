"""Static C28 checks only. Never load or execute proposed source."""
import ast
import hashlib
from pathlib import Path

RAW = (Path(__file__).resolve().parents[1] /
       "docs/qualification/int10c/external_supervisor.py.proposed").read_bytes()

def tree():
    return ast.parse(RAW.decode("utf-8"))

def supervisor():
    return next(n for n in tree().body
                if isinstance(n, ast.FunctionDef) and n.name == "supervise")

def calls(node, name):
    return [n for n in ast.walk(node) if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Name) and n.func.id == name]

def test_exact_reviewed_blob():
    assert hashlib.sha1(f"blob {len(RAW)}".encode() + b"\x00" + RAW).hexdigest() == "5bfc443bf9d51fc9a71e3a683e9750fef85c68df"

def test_no_top_level_execution():
    assert all(isinstance(n, (ast.Import, ast.FunctionDef)) or
               (isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant)
                and isinstance(n.value.value, str)) for n in tree().body)

def test_observation_error_has_distinct_outcome():
    fn = supervisor()
    obs = next(n for n in fn.body if isinstance(n, ast.Try)
               and calls(n, "observe_runner"))
    assert any(isinstance(n, ast.Constant) and n.value == "OBSERVATION_ERROR"
               for h in obs.handlers for n in ast.walk(h))
    assert not any(isinstance(n, ast.Return) for h in obs.handlers for n in ast.walk(h))
    assert any(isinstance(n, ast.Try) and calls(n, "destroy_domain")
               for n in fn.body[fn.body.index(obs)+1:])

def test_cleanup_rechecks_after_stop():
    cleanup = next(n for n in supervisor().body if isinstance(n, ast.Try)
                   and calls(n, "destroy_domain"))
    stop = next(i for i,n in enumerate(cleanup.body) if calls(n,"stop_admission"))
    destroy = next(i for i,n in enumerate(cleanup.body) if calls(n,"destroy_domain"))
    assert stop < destroy
    checks = [n for n in cleanup.body[stop+1:destroy]
              if isinstance(n, ast.If) and calls(n.test,"owned_before")]
    assert len(checks) == 1 and any(isinstance(n,ast.Return) for n in checks[0].body)

def test_quarantine_is_readback_only():
    fn = supervisor()
    assert len(calls(fn,"quarantine_readback")) == 1
    assert not calls(fn,"quarantine")
    assert not any(n.finalbody for n in ast.walk(fn) if isinstance(n,ast.Try))

def test_explicit_states_and_separate_result():
    fn = supervisor()
    values = {n.value for n in ast.walk(fn) if isinstance(n,ast.Constant)
              and isinstance(n.value,str)}
    assert {"RUNNING","COMPLETED","FAILED","INTERRUPTED","UNKNOWN_STATE",
            "WORK_DEADLINE","OBSERVATION_ERROR"} <= values
    result = next(n for n in fn.body if isinstance(n,ast.FunctionDef) and n.name=="result")
    d = next(n.value for n in result.body if isinstance(n,ast.Return))
    fields = {k.value:v for k,v in zip(d.keys,d.values)}
    assert {"workload_outcome","absence_reported","quarantine_reported"} <= fields.keys()
    for k in ("runtime_attested","launch_authorized"):
        assert isinstance(fields[k],ast.Constant) and fields[k].value is False
