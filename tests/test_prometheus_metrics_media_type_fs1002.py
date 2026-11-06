"""Contract regression for Prometheus metrics response media types."""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_prometheus_metrics_content_type_contract():
    for service in ("core", "twin"):
        source = ROOT / "app" / service / "main.py"
        tree = ast.parse(source.read_text())
        imports = [
            n for n in ast.walk(tree)
            if isinstance(n, ast.ImportFrom)
            and n.module == "fastapi.responses"
            and any(a.name == "PlainTextResponse" for a in n.names)
        ]
        assert imports, f"{service}: PlainTextResponse import missing"
        routes = [
            n for n in tree.body
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
            and n.name == "metrics"
        ]
        assert len(routes) == 1, f"{service}: expected one metrics route"
        dec = routes[0].decorator_list
        assert any(
            isinstance(d, ast.Call)
            and any(isinstance(a, ast.Constant) and a.value == "/metrics" for a in d.args)
            and any(k.arg == "response_class" and isinstance(k.value, ast.Name) and k.value.id == "PlainTextResponse" for k in d.keywords)
            for d in dec
        ), f"{service}: /metrics must expose text/plain"
