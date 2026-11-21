"""Core command must not resolve without an independent qualified authority."""
import ast
from pathlib import Path
from types import SimpleNamespace
from contextlib import contextmanager
import pytest

class Refusal(Exception):
    def __init__(self, status_code, detail):
        self.status_code = status_code
        self.detail = detail

@pytest.mark.parametrize("mode", ["DEMO", "REPLAY", "STORY", "LIVE"])
@pytest.mark.parametrize("state", ["RUNNING", "BLOCKED"])
def test_core_refuses_unqualified_resolve_before_mutation(mode, state):
    source = Path(__file__).resolve().parents[1] / "app/core/main.py"
    fn = next(n for n in ast.parse(source.read_text()).body
              if isinstance(n, ast.FunctionDef) and n.name == "command")
    fn.decorator_list = []
    calls = []
    class Cursor:
        def execute(self, sql, args):
            calls.append(sql)
            assert sql.startswith("select status,version,mode")
            return SimpleNamespace(fetchone=lambda: (state, 7, mode))
    @contextmanager
    def db():
        yield Cursor()
    ns = dict(Command=object, Header=lambda **k: None, auth=lambda x: None,
              bearer=lambda x: x, db=db, HTTPException=Refusal)
    exec(compile(ast.Module(body=[fn], type_ignores=[]), str(source), "exec"), ns)
    with pytest.raises(Refusal) as exc:
        ns["command"]("run-01", SimpleNamespace(command="RESOLVE",
            expected_version=7, idempotency_key="replayed"), "inert")
    assert exc.value.status_code == 403
    assert len(calls) == 1
