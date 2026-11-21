import copy
import unittest
from pathlib import Path
from preflight import validate

def fixture():
    services = {}
    for name in ("gamma", "core", "demo"):
        services[name] = dict(image="example.invalid/fixture@sha256:" + "a"*64,
            user="65532:65532", read_only=True, cap_drop=["ALL"],
            security_opt=["no-new-privileges:true"],
            networks={"backend":None}, environment={"FIXTURE_ROLE":name},
            command=["python","/fixture.py"],
            volumes=[dict(type="bind", source=str(Path(__file__).resolve().with_name("fixture.py")), target="/fixture.py", read_only=True)])
    for service in services.values():
        service["healthcheck"] = dict(test=["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=2)"], retries=12)
    services["gamma"]["depends_on"] = {"core":{"condition":"service_healthy"}}
    services["gamma"]["networks"]["edge"] = None
    services["gamma"]["ports"] = [dict(host_ip="127.0.0.1", target=8080, published="0", protocol="tcp")]
    return dict(services=services, networks={"edge":{}, "backend":{"internal":True}})

class IsolationTests(unittest.TestCase):
    def test_valid(self):
        validate(fixture())
    def test_base(self):
        c = fixture()
        del c["services"]["demo"]
        validate(c)
    def test_rejections(self):
        for field, value in [
            ("healthcheck", None), ("healthcheck", {"test":["CMD","true"],"retries":12}),
            ("depends_on", {"demo":{"condition":"service_started"}}),
            ("cap_add", ["SYS_ADMIN"]), ("cap_drop", []),
            ("security_opt", ["seccomp:unconfined"]), ("read_only", "true"),
            ("privileged", True), ("network_mode","host"),
            ("networks", {"edge":None}), ("image","python:latest"),
            ("volumes",[dict(type="bind",source="/",target="/fixture.py",read_only=True)]),
            ("environment",{"FIXTURE_ROLE":"gamma","TOKEN":"synthetic"}),
            ("ports",[dict(host_ip="127.0.0.1",target=8080,published="0",protocol="udp")]),
            ("ports",[dict(host_ip="0.0.0.0",target=8080,published="0",protocol="tcp")]),
            ("ports",[dict(host_ip="127.0.0.1",target="8080",published="0",protocol="tcp")]),
        ]:
            with self.subTest(field=field,value=value):
                c = fixture()
                c["services"]["gamma"][field] = value
                with self.assertRaises(ValueError):
                    validate(c)
    def test_network_driver_opts(self):
        c = fixture()
        c["networks"]["edge"]["driver_opts"] = {"com.docker.network.bridge.host_binding_ipv4": "0.0.0.0"}
        with self.assertRaises(ValueError):
            validate(c)
    def test_network_external(self):
        c = fixture()
        c["networks"]["edge"]["external"] = True
        with self.assertRaises(ValueError):
            validate(c)

if __name__ == "__main__":
    unittest.main()
