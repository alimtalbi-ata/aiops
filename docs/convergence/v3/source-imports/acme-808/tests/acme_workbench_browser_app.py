"""Test-only ASGI Portal: force every upstream service access to fail closed."""
from portal import main

def _deny(*args, **kwargs):
    raise RuntimeError("ACME_BROWSER_TEST_EXTERNAL_SERVICE_DENIED")

main.get_json = _deny
main.post_json = _deny
main._get = lambda *args, **kwargs: {"status": "UNKNOWN"}
main._runs = lambda *args, **kwargs: []
app = main.app
